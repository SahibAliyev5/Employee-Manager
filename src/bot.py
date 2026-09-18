import asyncio
import logging
from functools import wraps
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)

import config
import db
import agent

# Configure standard console logging
logging.basicConfig(
    format="%(asctime)s - [%(levelname)s] - %(name)s: %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("ems_bot")


def authorized_only(func):
    """Restricts access to Telegram IDs registered in the authorized_users table."""
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        if not update.effective_user or not update.message:
            return

        telegram_id = update.effective_user.id
        employee = await db.get_authorized_employee(telegram_id)

        if not employee:
            logger.warning("Unauthorized access attempt from Telegram ID: %s", telegram_id)
            await update.message.reply_text(
                f"⛔ Access Denied. Your Telegram ID (`{telegram_id}`) is not registered.",
                parse_mode="Markdown",
            )
            return

        context.user_data["employee"] = employee
        return await func(update, context, *args, **kwargs)
    return wrapper


@authorized_only
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    emp = context.user_data["employee"]
    logger.info("User authenticated: %s (ID: %s)", emp["name"], emp["employee_id"])
    await update.message.reply_text(
        f"👋 Welcome, *{emp['name']}*!\n"
        f"• Role: `{emp['role']}`\n"
        f"• Department: `{emp.get('department') or 'General'}`\n\n"
        "Ask me questions about tasks, employees, or status updates.\n"
        "Use /reset to clear conversational memory.",
        parse_mode="Markdown",
    )


@authorized_only
async def reset_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    emp = context.user_data["employee"]
    new_thread_id = await db.reset_active_thread(emp["employee_id"])
    logger.info("Reset session for employee %s (New Thread: %s)", emp["employee_id"], new_thread_id)
    await update.message.reply_text("🔄 Session history cleared. A new thread has been created.")


@authorized_only
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    emp = context.user_data["employee"]
    emp_id = emp["employee_id"]
    prompt = update.message.text

    lock = agent.EMPLOYEE_LOCKS[emp_id]
    if lock.locked():
        await update.message.reply_text("⏳ Still processing your previous query, please wait...")
        return

    async with lock:
        # Periodic typing indicator
        async def typing_pulse():
            try:
                while True:
                    await update.message.chat.send_action(action="typing")
                    await asyncio.sleep(4)
            except asyncio.CancelledError:
                pass

        pulse = asyncio.create_task(typing_pulse())

        try:
            logger.info("Processing message from %s: %s", emp["name"], prompt[:50])
            reply = await agent.process_user_turn(emp, prompt)
            await update.message.reply_text(reply)
        except Exception as e:
            logger.exception("Error processing turn for employee %s", emp_id)
            # Only try to reply if it is NOT a Telegram network error
            import telegram.error
            if not isinstance(e, telegram.error.NetworkError):
                try:
                    await update.message.reply_text(f"⚠️ Execution Failure: {str(e)}")
                except Exception:
                    pass # Suppress secondary failures
        finally:
            pulse.cancel()


async def startup(app):
    logger.info("Initializing database connection pool...")
    await db.init_pool()
    logger.info("Database pool initialized successfully.")

    logger.info("Connecting to FastMCP server subprocess...")
    await agent.init_mcp()
    logger.info("FastMCP server connected and ready.")

    logger.info("Telegram bot is running and listening for updates.")


async def shutdown(app):
    logger.info("Shutting down services...")
    await agent.close_mcp()
    logger.info("FastMCP server connection closed.")
    await db.close_pool()
    logger.info("Database pool closed. Shutdown complete.")


if __name__ == "__main__":
    app = (
        ApplicationBuilder()
        .token(config.TELEGRAM_BOT_TOKEN)
        .post_init(startup)
        .post_shutdown(shutdown)
        .build()
    )

    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("reset", reset_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    app.run_polling()