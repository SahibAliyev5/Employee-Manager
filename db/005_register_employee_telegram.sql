-- CREATE OR REPLACE PROCEDURE register_employee_telegram(
--     p_name VARCHAR,
--     p_department VARCHAR,
--     p_role VARCHAR,
--     p_telegram_id BIGINT
-- )
-- LANGUAGE plpgsql
-- AS $$
-- DECLARE
--     v_dept_id INT;
--     v_role_id INT;
--     v_emp_id INT;
-- BEGIN
--     -- 1. Ensure Department exists
--     INSERT INTO departments (name)
--     VALUES (p_department)
--     ON CONFLICT (name) DO NOTHING;
--     SELECT id INTO v_dept_id FROM departments WHERE name = p_department;

--     -- 2. Ensure Role exists
--     INSERT INTO roles (name)
--     VALUES (p_role)
--     ON CONFLICT (name) DO NOTHING;
--     SELECT id INTO v_role_id FROM roles WHERE name = p_role;

--     -- 3. Create Employee
--     INSERT INTO employees (name, department_id, role_id)
--     VALUES (p_name, v_dept_id, v_role_id)
--     RETURNING id INTO v_emp_id;

--     -- 4. Authorize Telegram Account
--     INSERT INTO authorized_users (telegram_id, employee_id)
--     VALUES (p_telegram_id, v_emp_id)
--     ON CONFLICT (telegram_id) DO UPDATE
--     SET employee_id = EXCLUDED.employee_id;

--     RAISE NOTICE 'Successfully registered % (ID: %) with Telegram ID %', p_name, v_emp_id, p_telegram_id;
-- END;
-- $$;


-- CALL register_employee_telegram('Sahib Aliyev', 'Management', 'Admin', 2052125200);

TRUNCATE TABLE authorized_users;

INSERT INTO authorized_users (telegram_id, employee_id)
VALUES (2052125200, 2)
ON CONFLICT (telegram_id) DO UPDATE 
SET employee_id = EXCLUDED.employee_id;
