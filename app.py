from flask import Flask, render_template, request, redirect, url_for, session
import pandas as pd
import mysql.connector
import os

app = Flask(__name__)
app.secret_key = "smartpayroll"

# ================= MYSQL CONNECTION =================

db = mysql.connector.connect(
    host="localhost",
    user="root",
    password="root123",
    database="payroll_db"
)

cursor = db.cursor()

# ================= UPLOAD FOLDER =================

UPLOAD_FOLDER = "uploads"

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER


# ====================================================
# LOGIN PAGE
# ====================================================

@app.route('/')
def home():
    return render_template('login.html')


# ====================================================
# LOGIN AUTH
# ====================================================

@app.route('/login', methods=['POST'])
def login():

    username = request.form['username']
    password = request.form['password']

    if username == "admin@smartpay.com" and password == "smart123":

        session['user'] = username

        return redirect(url_for('dashboard'))

    return "Invalid Login Credentials"


# ====================================================
# DASHBOARD
# ====================================================

@app.route('/dashboard')
def dashboard():

    if 'user' not in session:
        return redirect('/')

    # FETCH EMPLOYEES

    cursor.execute("SELECT * FROM employees")
    employees = cursor.fetchall()

    # FETCH LEAVES

    cursor.execute("SELECT * FROM leaves")
    leaves = cursor.fetchall()

    cursor.execute("""
    SELECT COUNT(*) 
    FROM leaves 
    WHERE LOWER(status) = 'pending'
    """)
    
    pending_leaves = cursor.fetchone()[0]

    # ANALYTICS

    total_employees = len(employees)

    total_payroll = (
        sum(emp[13] or 0 for emp in employees)
        if employees else 0
    )

    highest_salary = (
        max(emp[13] or 0 for emp in employees)
        if employees else 0
    )

    average_salary = round(
        total_payroll / total_employees,
        2
    ) if total_employees > 0 else 0

    return render_template(
        'dashboard.html',

        employees=employees,
        leaves=leaves,

        total_employees=total_employees,
        total_payroll=total_payroll,
        highest_salary=highest_salary,
        average_salary=average_salary,
        pending_leaves=pending_leaves
    )


# ====================================================
# EMPLOYEES PAGE
# ====================================================

@app.route('/employees')
def employees_page():

    if 'user' not in session:
        return redirect('/')

    search = request.args.get('search')

    department = request.args.get('department')

    status = request.args.get('status')

    sql = "SELECT * FROM employees WHERE 1=1"

    values = []

    # SEARCH

    if search and search != "":
        sql += " AND name LIKE %s"
        values.append(f"%{search}%")

    # DEPARTMENT FILTER

    if department and department != "All":
        sql += " AND department=%s"
        values.append(department)

    # STATUS FILTER

    if status and status != "All":
        sql += " AND payroll_status=%s"
        values.append(status)

    cursor.execute(sql, tuple(values))

    employees = cursor.fetchall()

    return render_template(
        'employees.html',
        employees=employees
    )

# ====================================================
# ADD EMPLOYEE PAGE
# ====================================================

@app.route('/add_employee_page')
def add_employee_page():

    if 'user' not in session:
        return redirect('/')

    return render_template('add_employee.html')

# ====================================================
# PAYROLL PAGE
# ====================================================

@app.route('/payroll')
def payroll_page():

    if 'user' not in session:
        return redirect('/')

    department = request.args.get('department')

    sql = "SELECT * FROM employees"

    values = []

    if department and department != "All":
        sql += " WHERE department=%s"
        values.append(department)

    cursor.execute(sql, tuple(values))

    employees = cursor.fetchall()

    total_payroll = 0

    for emp in employees:

        if emp[13]:
            total_payroll += float(emp[13])

    return render_template(
        'payroll.html',
        employees=employees,
        total_payroll=total_payroll
    )
   
# ====================================================
# GENERATE PAYROLL
# ====================================================

@app.route('/generate_payroll')
def generate_payroll():

    cursor.execute(
        "UPDATE employees SET payroll_status='Processed'"
    )

    db.commit()

    return redirect(url_for('payroll_page'))


# ====================================================
# LEAVE PAGE
# ====================================================

@app.route('/leave')
def leave_page():

    if 'user' not in session:
        return redirect('/')

    cursor.execute("SELECT * FROM leaves")

    leaves = cursor.fetchall()

    return render_template(
        'leave.html',
        leaves=leaves
    )


# ====================================================
# REPORTS PAGE
# ====================================================

@app.route('/reports')
def reports_page():

    if 'user' not in session:
        return redirect('/')

    cursor.execute("SELECT * FROM employees")

    employees = cursor.fetchall()

    total_employees = len(employees)

    total_payroll = 0

    salaries = []

    for emp in employees:

        if emp[13]:

            salary = float(emp[13])

            total_payroll += salary

            salaries.append(salary)

    highest_salary = max(salaries) if salaries else 0

    average_salary = (
        round(total_payroll / total_employees, 2)
        if total_employees > 0 else 0
    )

    return render_template(
        'reports.html',

        employees=employees,

        total_employees=total_employees,
        total_payroll=total_payroll,
        highest_salary=highest_salary,
        average_salary=average_salary
    )
# ====================================================
# UPLOAD EXCEL
# ====================================================

@app.route('/upload_excel', methods=['GET', 'POST'])
def upload_excel():

    if 'user' not in session:
        return redirect('/')

    if request.method == 'POST':

        print("UPLOAD STARTED")

        if 'file' not in request.files:
            return "No File Found"

        file = request.files['file']

        if file.filename == "":
            return "No File Selected"

        filepath = os.path.join(
            app.config["UPLOAD_FOLDER"],
            file.filename
        )

        file.save(filepath)

        # READ EXCEL

        data = pd.read_excel(filepath)

        # CLEAN COLUMN NAMES

        data.columns = data.columns.str.strip().str.lower()

        for i, row in data.iterrows():

            try:

                name = row['name']
                department = row['department']

                basic_salary = float(row['salary'])

                bonus = float(row['bonus'])

                deduction = float(row['deduction'])

                working_days = float(row['working_days'])

                overtime_hours = float(row['overtime_hours'])

                leave_days = float(row['leave_days'])

                # PAYROLL ENGINE

                overtime_rate = 500

                overtime_pay = overtime_hours * overtime_rate

                leave_deduction = leave_days * 1000

                tax = basic_salary * 0.10

                pf = basic_salary * 0.05

                payroll_status = "Processed"

                net_salary = (
                    basic_salary
                    + bonus
                    + overtime_pay
                    - deduction
                    - leave_deduction
                    - tax
                    - pf
                )

                # DUPLICATE CHECK

                check_sql = """
                SELECT * FROM employees
                WHERE name=%s AND department=%s
                """

                check_values = (name, department)

                cursor.execute(check_sql, check_values)

                existing_employee = cursor.fetchone()

                if existing_employee:
                    continue

                # INSERT DATA

                sql = """
                INSERT INTO employees
                (
                    name,
                    department,
                    basic_salary,
                    bonus,
                    deduction,
                    overtime_hours,
                    working_days,
                    leave_days,
                    tax,
                    pf,
                    overtime_pay,
                    leave_deduction,
                    payroll_status,
                    net_salary
                )

                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                """

                values = (
                    name,
                    department,
                    basic_salary,
                    bonus,
                    deduction,
                    overtime_hours,
                    working_days,
                    leave_days,
                    tax,
                    pf,
                    overtime_pay,
                    leave_deduction,
                    payroll_status,
                    net_salary
                )

                cursor.execute(sql, values)

            except Exception as e:

                print("ERROR:", e)

        db.commit()

        return redirect(url_for('employees_page'))

    return render_template('upload_excel.html')


# ====================================================
# ADD EMPLOYEE
# ====================================================

@app.route('/add_employee', methods=['POST'])
def add_employee():

    name = request.form['name']

    department = request.form['department']

    basic_salary = float(request.form['salary'])

    bonus = float(request.form['bonus'])

    deduction = float(request.form['deduction'])

    working_days = float(request.form['working_days'])

    overtime_hours = float(request.form['overtime_hours'])

    leave_days = float(request.form['leave_days'])

    # PAYROLL ENGINE

    overtime_rate = 500

    overtime_pay = overtime_hours * overtime_rate

    leave_deduction = leave_days * 1000

    tax = basic_salary * 0.10

    pf = basic_salary * 0.05

    payroll_status = "Processed"

    net_salary = (

        basic_salary
        + bonus
        + overtime_pay
        - deduction
        - leave_deduction
        - tax
        - pf
)

    sql = """
    INSERT INTO employees
    (
        name,
        department,
        basic_salary,
        bonus,
        deduction,
        overtime_hours,
        working_days,
        leave_days,
        tax,
        pf,
        overtime_pay,
        leave_deduction,
        payroll_status,
        net_salary
    )

    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
    """

    values = (
        name,
        department,
        basic_salary,
        bonus,
        deduction,
        overtime_hours,
        working_days,
        leave_days,
        tax,
        pf,
        overtime_pay,
        leave_deduction,
        payroll_status,
        net_salary
    )

    cursor.execute(sql, values)

    db.commit()

    return redirect(url_for('employees_page'))

@app.route('/update_old_salaries')
def update_old_salaries():

    cursor.execute("SELECT * FROM employees")

    employees = cursor.fetchall()

    for emp in employees:

        emp_id = emp[0]

        basic_salary = float(emp[3] or 0)
        bonus = float(emp[4] or 0)
        deduction = float(emp[5] or 0)
        overtime_hours = float(emp[6] or 0)
        leave_days = float(emp[8] or 0)

        overtime_pay = overtime_hours * 500
        leave_deduction = leave_days * 1000
        tax = basic_salary * 0.10
        pf = basic_salary * 0.05

        net_salary = (
            basic_salary
            + bonus
            + overtime_pay
            - deduction
            - leave_deduction
            - tax
            - pf
        )

        sql = """
        UPDATE employees
        SET net_salary=%s
        WHERE id=%s
        """

        cursor.execute(sql, (net_salary, emp_id))

    db.commit()

    return "Old salaries updated successfully"

# ====================================================
# EDIT EMPLOYEE
# ====================================================

@app.route('/edit_employee/<int:id>', methods=['GET', 'POST'])
def edit_employee(id):

    if request.method == 'POST':

        name = request.form['name']

        department = request.form['department']

        salary = request.form['salary']

        bonus = request.form['bonus']

        deduction = request.form['deduction']

        sql = """
        UPDATE employees
        SET
        name=%s,
        department=%s,
        basic_salary=%s,
        bonus=%s,
        deduction=%s
        WHERE id=%s
        """

        values = (
            name,
            department,
            salary,
            bonus,
            deduction,
            id
        )

        cursor.execute(sql, values)

        db.commit()

        return redirect(url_for('employees_page'))

    cursor.execute(
        "SELECT * FROM employees WHERE id=%s",
        (id,)
    )

    employee = cursor.fetchone()

    return render_template(
        'edit_employee.html',
        employee=employee
    )


# ====================================================
# DELETE EMPLOYEE
# ====================================================

@app.route('/delete_employee/<int:id>')
def delete_employee(id):

    cursor.execute(
        "DELETE FROM employees WHERE id=%s",
        (id,)
    )

    db.commit()

    return redirect(url_for('employees_page'))


# ====================================================
# PAYSLIP
# ====================================================

@app.route('/payslip/<int:id>')
def payslip(id):

    cursor.execute(
        "SELECT * FROM employees WHERE id=%s",
        (id,)
    )

    employee = cursor.fetchone()

    return render_template(
        'payslip.html',
        employee=employee
    )
# ====================================================
# VIEW EMPLOYEE DETAILS
# ====================================================

@app.route('/employee/<int:id>')
def employee_details(id):

    cursor.execute(
        "SELECT * FROM employees WHERE id=%s",
        (id,)
    )

    employee = cursor.fetchone()

    return render_template(
        'employee_details.html',
        employee=employee
    )


# ====================================================
# APPLY LEAVE
# ====================================================

@app.route('/apply_leave', methods=['POST'])
def apply_leave():

    employee_name = request.form['employee_name']

    leave_days = request.form['leave_days']

    reason = request.form['reason']

    status = "Pending"

    sql = """
    INSERT INTO leaves
    (
        employee_name,
        leave_days,
        reason,
        status
    )

    VALUES (%s,%s,%s,%s)
    """

    values = (
        employee_name,
        leave_days,
        reason,
        status
    )

    cursor.execute(sql, values)

    db.commit()

    return redirect(url_for('leave_page'))


# ====================================================
# APPROVE LEAVE
# ====================================================

@app.route('/approve_leave/<int:id>')
def approve_leave(id):

    sql = """
    UPDATE leaves
    SET status='Approved'
    WHERE id=%s
    """

    cursor.execute(sql, (id,))

    db.commit()

    return redirect(url_for('leave_page'))


# ====================================================
# REJECT LEAVE
# ====================================================

@app.route('/reject_leave/<int:id>')
def reject_leave(id):

    sql = """
    UPDATE leaves
    SET status='Rejected'
    WHERE id=%s
    """

    cursor.execute(sql, (id,))

    db.commit()

    return redirect(url_for('leave_page'))


# ====================================================
# LOGOUT
# ====================================================

@app.route('/logout')
def logout():

    session.pop('user', None)

    return redirect('/')


# ====================================================
# RUN APP
# ====================================================

if __name__ == '__main__':
    app.run(debug=True)