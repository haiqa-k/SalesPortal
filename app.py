from flask import Flask, render_template, request, redirect, url_for, session
import pyodbc
import bcrypt

app = Flask(__name__)
app.secret_key = "supersecretkey"

# SQL Server connection
conn_str = (
    "Driver={ODBC Driver 17 for SQL Server};"
    "Server=DESKTOP-64AVK23;"
    "Database=Sales;"
    "Trusted_Connection=yes;"
)
conn = pyodbc.connect(conn_str)

@app.route("/", methods=["GET", "POST"])
def login():
    message = ""

    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        cursor = conn.cursor()
        cursor.execute("""
            SELECT UserID, FirstName, LastName, PasswordHash, Role
            FROM Users
            WHERE Username=? AND IsActive=1
        """, (username,))
        row = cursor.fetchone()

        if row:
            # Unpack all values properly
            user_id, first_name, last_name, stored_hash, role = row

            if bcrypt.checkpw(password.encode("utf-8"), stored_hash.encode("utf-8")):
                # Store both names in session
                session["user_id"] = user_id
                session["username"] = username
                session["first_name"] = first_name
                session["last_name"] = last_name
                session["role"] = role

                if role == "EDO":
                    return redirect(url_for("edo_dashboard"))
                elif role == "Team Lead":
                    return redirect(url_for("teamlead_dashboard"))
                elif role == "Head":
                    return redirect(url_for("head_dashboard"))
            else:
                message = "Incorrect password"
        else:
            message = "User not found or inactive"

    return render_template("login.html", message=message)


@app.route("/edo")
def edo_dashboard():
    edo_name = f"{session.get('first_name', '')} {session.get('last_name', '')}".strip()

    cursor = conn.cursor()
    cursor.execute("""
        SELECT PipelineID, [Vertical], [Account Name], [Product], [Region], [MRC],
               [Contract Duration (Months)], [ARR], [Project OTC], [Total Project Revenue],
               [Estimated Closure Date], [Estimated Closure Month], [Sales Cycle Status],
               [Account Manager], [Next Action]
        FROM Pipelines
        WHERE [Account Manager] = ?
    """, (edo_name,))
    pipelines = cursor.fetchall()

    return render_template("edo.html", edo_name=edo_name, pipelines=pipelines)


@app.route("/pipeline/<int:pipeline_id>/edit", methods=["GET", "POST"])
def edit_pipeline(pipeline_id):
    cursor = conn.cursor()

    if request.method == "POST":
        closure_date_input = request.form.get("closure_date")
        next_action = request.form.get("next_action")
        status = request.form.get("status")

        updates = []
        params = []

        # Only update date/month if user picked a date
        if closure_date_input:
            import datetime
            dt = datetime.datetime.strptime(closure_date_input, "%Y-%m-%d")
            updates.append("[Estimated Closure Date] = ?")
            params.append(int(dt.day))
            updates.append("[Estimated Closure Month] = ?")
            params.append(dt.strftime("%B"))

        # Only update Next Action if provided
        if next_action:
            updates.append("[Next Action] = ?")
            params.append(next_action)

        # Only update Sales Cycle Status if provided
        if status:
            updates.append("[Sales Cycle Status] = ?")
            params.append(status)

        # Build dynamic SQL
        if updates:  # only run update if something changed
            sql = f"UPDATE Pipelines SET {', '.join(updates)} WHERE PipelineID = ?"
            params.append(pipeline_id)
            cursor.execute(sql, params)
            conn.commit()

        return redirect(url_for("edo_dashboard"))

    # Load pipeline for editing
    cursor.execute("""
        SELECT PipelineID, [Account Name], [Estimated Closure Date], 
               [Estimated Closure Month], [Next Action], [Sales Cycle Status]
        FROM Pipelines
        WHERE PipelineID = ?
    """, (pipeline_id,))
    pipeline = cursor.fetchone()

    statuses = [
        "Customer Visit (20%)",
        "Ask for Proposal (40%)",
        "Negotiations (60%)",
        "Documentation/Acceptance/Processing (80%)",
        "System Entry/Revenue Locked (100%)"
    ]

    return render_template("edit_pipeline.html", pipeline=pipeline, statuses=statuses)


@app.route("/teamlead", methods=["GET"])
def teamlead_dashboard():

    teamlead_id = session.get("user_id")
    first_name = session.get("first_name")

    # Default view = all EDOs
    selected_edo = request.args.get("edo_id", "all")

    cursor = conn.cursor()


    # =========================
    # SUMMARY METRICS
    # =========================

    cursor.execute("""
        SELECT 
            SUM(p.[MRC]) AS TotalMRC,
            SUM(p.[Project OTC]) AS TotalOTC,
            SUM(p.[Total Project Revenue]) AS TotalRevenue,
            COUNT(*) AS ActivePipelines
        FROM Pipelines p

        JOIN Users u
            ON p.[Account Manager] =
               (u.FirstName + ' ' + u.LastName)

        WHERE u.ManagerID = ?
    """, (teamlead_id,))


    summary_row = cursor.fetchone()


    summary = {

        "TotalMRC":
            summary_row[0] or 0,

        "TotalOTC":
            summary_row[1] or 0,

        "TotalRevenue":
            summary_row[2] or 0,

        "ActivePipelines":
            summary_row[3] or 0

    }



    # =========================
    # EDO LIST
    # =========================

    cursor.execute("""
        SELECT
            UserID,
            FirstName,
            LastName

        FROM Users

        WHERE ManagerID = ?
    """, (teamlead_id,))


    edos = [

        {
            "UserID": row[0],

            "FullName":
                f"{row[1]} {row[2]}"
        }

        for row in cursor.fetchall()

    ]



    # =========================
    # REVENUE PER EDO
    # =========================

    cursor.execute("""
        SELECT
            (u.FirstName + ' ' + u.LastName) AS FullName,

            SUM(p.[Total Project Revenue])

        FROM Pipelines p

        JOIN Users u
            ON p.[Account Manager] =
               (u.FirstName + ' ' + u.LastName)

        WHERE u.ManagerID = ?

        GROUP BY
            (u.FirstName + ' ' + u.LastName)
    """, (teamlead_id,))


    edo_names = []
    edo_revenues = []


    for row in cursor.fetchall():

        edo_names.append(
            row[0]
        )

        edo_revenues.append(
            row[1] or 0
        )



    # =========================
    # PIPELINE STATUS
    # =========================

    cursor.execute("""
        SELECT
            p.[Sales Cycle Status],
            COUNT(*)

        FROM Pipelines p

        JOIN Users u
            ON p.[Account Manager] =
               (u.FirstName + ' ' + u.LastName)

        WHERE u.ManagerID = ?

        GROUP BY
            p.[Sales Cycle Status]
    """, (teamlead_id,))


    status_labels = []
    status_counts = []


    for row in cursor.fetchall():

        status_labels.append(
            row[0]
        )

        status_counts.append(
            row[1]
        )



    # =========================
    # PIPELINES
    # =========================

    pipelines = []


    # -------------------------
    # ALL EDOs
    # -------------------------

    if selected_edo == "all":

        cursor.execute("""
            SELECT
                p.[Account Manager],
                p.[Account Name],
                p.[MRC],
                p.[Total Project Revenue],
                p.[Sales Cycle Status],
                p.[Next Action]

            FROM Pipelines p

            JOIN Users u
                ON p.[Account Manager] =
                   (u.FirstName + ' ' + u.LastName)

            WHERE u.ManagerID = ?

            ORDER BY
                p.[Account Manager],
                p.[Account Name]
        """, (teamlead_id,))


        pipelines = [

            {
                "AccountManager":
                    row[0],

                "AccountName":
                    row[1],

                "MRC":
                    row[2],

                "TotalProjectRevenue":
                    row[3],

                "SalesCycleStatus":
                    row[4],

                "NextAction":
                    row[5]
            }

            for row in cursor.fetchall()

        ]


    # -------------------------
    # SPECIFIC EDO
    # -------------------------

    elif selected_edo:

        try:

            selected_edo = int(
                selected_edo
            )

        except ValueError:

            selected_edo = "all"


        if selected_edo != "all":

            selected_edo_name = next(

                (
                    edo["FullName"]

                    for edo in edos

                    if edo["UserID"] ==
                       selected_edo
                ),

                None

            )


            if selected_edo_name:

                cursor.execute("""
                    SELECT
                        p.[Account Manager],
                        p.[Account Name],
                        p.[MRC],
                        p.[Total Project Revenue],
                        p.[Sales Cycle Status],
                        p.[Next Action]

                    FROM Pipelines p

                    WHERE
                        p.[Account Manager] = ?

                    ORDER BY
                        p.[Account Name]
                """, (selected_edo_name,))


                pipelines = [

                    {
                        "AccountManager":
                            row[0],

                        "AccountName":
                            row[1],

                        "MRC":
                            row[2],

                        "TotalProjectRevenue":
                            row[3],

                        "SalesCycleStatus":
                            row[4],

                        "NextAction":
                            row[5]
                    }

                    for row in cursor.fetchall()

                ]



    # =========================
    # RENDER PAGE
    # =========================

    return render_template(

        "teamlead.html",

        first_name=first_name,

        summary=summary,

        edos=edos,

        selected_edo=selected_edo,

        pipelines=pipelines,

        edo_names=edo_names,

        edo_revenues=edo_revenues,

        status_labels=status_labels,

        status_counts=status_counts

    )


@app.route("/head")
def head_dashboard():
    return render_template("head.html", username=session.get("username"))



from flask import Flask, render_template, request, redirect, url_for
from datetime import datetime



@app.route("/add_pipeline", methods=["GET", "POST"])
def add_pipeline():
    if request.method == "GET":
        # Pass logged-in user's name to template
        edo_name = f"{session['first_name']} {session['last_name']}"
        return render_template("add_pipeline.html", edo_name=edo_name)

    # POST: receive form data
    vertical = request.form.get("vertical")
    account_name = request.form.get("account_name")
    product = request.form.get("product")
    region = request.form.get("region")

    mrc = request.form.get("mrc")
    contract_duration = request.form.get("contract_duration")
    arr = request.form.get("arr")
    project_otc = request.form.get("project_otc")
    total_project_revenue = request.form.get("total_project_revenue")
    closure_date = request.form.get("closure_date")
    sales_cycle_status = request.form.get("sales_cycle_status")
    next_action = request.form.get("next_action")

    # Convert numbers
    mrc = float(mrc) if mrc else None
    contract_duration = float(contract_duration) if contract_duration else None
    arr = float(arr) if arr else None
    project_otc = float(project_otc) if project_otc else None
    total_project_revenue = float(total_project_revenue) if total_project_revenue else None

    # Convert closure date into day + month
    closure_day = None
    closure_month = None
    if closure_date:
        closure_date_obj = datetime.strptime(closure_date, "%Y-%m-%d")
        closure_day = closure_date_obj.day
        closure_month = closure_date_obj.strftime("%B")

    # Auto-populate Account Manager from session
    account_manager = f"{session['first_name']} {session['last_name']}"

    # Insert into SQL Server
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO dbo.Pipelines
        (
            [Vertical],
            [Account Name],
            [Product],
            [Region],
            [MRC],
            [Contract Duration (Months)],
            [ARR],
            [Project OTC],
            [Total Project Revenue],
            [Estimated Closure Date],
            [Estimated Closure Month],
            [Sales Cycle Status],
            [Account Manager],
            [Next Action]
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """,
        vertical,
        account_name,
        product,
        region,
        mrc,
        contract_duration,
        arr,
        project_otc,
        total_project_revenue,
        closure_day,       # int day only
        closure_month,     # month name
        sales_cycle_status,
        account_manager,
        next_action
    )
    conn.commit()
    cursor.close()

    return redirect(url_for("edo_dashboard"))



    # Return to dashboard

    return redirect(url_for("edo_dashboard"))
if __name__ == "__main__":
    app.run(debug=True)
