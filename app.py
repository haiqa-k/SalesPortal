from flask import Flask, render_template, request, redirect, url_for, session
import pyodbc
import bcrypt
from datetime import datetime

app = Flask(__name__)
app.secret_key = "supersecretkey"

app.config["EXECUTIVE_DASHBOARD_ROLES"] = {
    "HOD",
    "Admin"
}

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
            SELECT EmpID, EmployeeName, FirstName, LastName, PasswordHash, Role
            FROM Users
            WHERE Username=? AND IsActive=1
        """, (username,))
        row = cursor.fetchone()

        if row:
            # Unpack all values properly
            user_id, employee_name, first_name, last_name, stored_hash, role = row

            if bcrypt.checkpw(password.encode("utf-8"), stored_hash.encode("utf-8")):
                # Store both names in session
                session["user_id"] = user_id
                session["username"] = username
                session["employee_name"] = employee_name
                session["first_name"] = first_name
                session["last_name"] = last_name
                session["role"] = role

                if role == "EDO":
                    return redirect(url_for("my_pipelines"))
                elif role == "Team Lead":
                    return redirect(url_for("teamlead_dashboard"))
                elif role == "Regional Manager":
                    return redirect(url_for("regional_manager_dashboard"))
                elif role == "Regional Head":
                    return redirect(url_for("regional_head_dashboard"))
                elif role in app.config.get(
                    "EXECUTIVE_DASHBOARD_ROLES",
                    set()
                ):
                    return redirect(
                        url_for("executive_dashboard")
                    )
                elif role == "Head":
                    return redirect(url_for("head_dashboard"))
            else:
                message = "Incorrect password"
        else:
            message = "User not found or inactive"

    return render_template("login.html", message=message)

@app.route("/change-password", methods=["GET", "POST"])
def change_password():

    message = ""
    message_type = ""


    if request.method == "POST":

        username = request.form["username"].strip()

        current_password = request.form["current_password"]

        new_password = request.form["new_password"]

        confirm_password = request.form["confirm_password"]


        # ----------------------------------
        # CHECK NEW PASSWORDS MATCH
        # ----------------------------------

        if new_password != confirm_password:

            message = "New passwords do not match."
            message_type = "error"

            return render_template(
                "change_password.html",
                message=message,
                message_type=message_type
            )


        # ----------------------------------
        # PASSWORD LENGTH
        # ----------------------------------

        if len(new_password) < 8:

            message = "New password must be at least 8 characters."
            message_type = "error"

            return render_template(
                "change_password.html",
                message=message,
                message_type=message_type
            )


        cursor = conn.cursor()


        # ----------------------------------
        # FIND USER
        # ----------------------------------

        cursor.execute("""
            SELECT
                EmpID,
                PasswordHash

            FROM Users

            WHERE
                Username = ?
                AND IsActive = 1
        """, (username,))

        row = cursor.fetchone()


        if not row:

            message = "Invalid username or current password."
            message_type = "error"

            return render_template(
                "change_password.html",
                message=message,
                message_type=message_type
            )


        user_id, stored_hash = row


        # ----------------------------------
        # VERIFY CURRENT PASSWORD
        # ----------------------------------

        if not bcrypt.checkpw(
            current_password.encode("utf-8"),
            stored_hash.encode("utf-8")
        ):

            message = "Invalid username or current password."
            message_type = "error"

            return render_template(
                "change_password.html",
                message=message,
                message_type=message_type
            )


        # ----------------------------------
        # DON'T ALLOW SAME PASSWORD
        # ----------------------------------

        if bcrypt.checkpw(
            new_password.encode("utf-8"),
            stored_hash.encode("utf-8")
        ):

            message = "New password must be different from your current password."
            message_type = "error"

            return render_template(
                "change_password.html",
                message=message,
                message_type=message_type
            )


        # ----------------------------------
        # HASH NEW PASSWORD
        # ----------------------------------

        new_hash = bcrypt.hashpw(
            new_password.encode("utf-8"),
            bcrypt.gensalt()
        ).decode("utf-8")


        # ----------------------------------
        # UPDATE DATABASE
        # ----------------------------------

        cursor.execute("""
            UPDATE Users

            SET PasswordHash = ?

            WHERE EmpID = ?
        """, (
            new_hash,
            user_id
        ))


        conn.commit()


        message = "Password changed successfully."
        message_type = "success"


    return render_template(
        "change_password.html",
        message=message,
        message_type=message_type
    )
@app.route("/my-pipelines")
def my_pipelines():

    if "user_id" not in session:
        return redirect(url_for("login"))

    edo_name = (
        session.get("employee_name")
        or f"{session.get('first_name', '')} {session.get('last_name', '')}".strip()
    )

    role = session.get("role")

    cursor = conn.cursor()


    # ========================================================
    # PIPELINES FOR THIS USER
    # ========================================================

    cursor.execute("""
        SELECT
            PipelineID,
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

        FROM Pipelines

        WHERE
            LTRIM(RTRIM([Account Manager])) =
            LTRIM(RTRIM(?))

        ORDER BY
            [Account Name]
    """, (edo_name,))

    pipelines = cursor.fetchall()


    # ========================================================
    # SUMMARY CARDS
    #
    # Includes ALL pipelines:
    # - Active
    # - 100%
    # - Lost
    # - Retired
    # ========================================================

    cursor.execute("""
        SELECT

            COALESCE(
                SUM([Total Project Revenue]),
                0
            ) AS TotalRevenue,

            COALESCE(
                SUM([MRC]),
                0
            ) AS TotalMRC,

            COALESCE(
                SUM([Project OTC]),
                0
            ) AS TotalOTC,

            COUNT(PipelineID) AS TotalPipelines

        FROM Pipelines

        WHERE
            LTRIM(RTRIM([Account Manager])) =
            LTRIM(RTRIM(?))

    """, (edo_name,))

    summary_row = cursor.fetchone()


    summary = {
        "TotalRevenue": summary_row[0] or 0,
        "TotalMRC": summary_row[1] or 0,
        "TotalOTC": summary_row[2] or 0,
        "TotalPipelines": summary_row[3] or 0
    }


    cursor.close()


    return render_template(
        "my_pipelines.html",

        edo_name=edo_name,
        role=role,

        pipelines=pipelines,
        summary=summary
    )

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
            updates.append("EstimatedClosureDateFull = ?")
            params.append(dt.date())
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

        return redirect(url_for("my_pipelines"))

    
    cursor.execute(
        """
        EXEC sys.sp_set_session_context
            @key = N'EditedBy',
            @value = ?
        """,
        session.get("employee_name")
    )
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
        "System Entry/Revenue Locked (100%)",
        "Lost to Competitor",
        "Retired - No Decision"

    ]

    return render_template("edit_pipeline.html", pipeline=pipeline, statuses=statuses)


@app.route("/teamlead", methods=["GET"])
def teamlead_dashboard():

    teamlead_id = session.get("user_id")
    first_name = session.get("first_name")

    # Default view = all team pipelines
    selected_edo = request.args.get("edo_id", "all")
    cursor = conn.cursor()


    # =========================
    # SUMMARY METRICS
    # Team Lead + assigned EDOs
    # =========================

    cursor.execute("""
        SELECT 
            SUM(p.[MRC]) AS TotalMRC,
            SUM(p.[Project OTC]) AS TotalOTC,
            SUM(p.[Total Project Revenue]) AS TotalRevenue,
            SUM(
                CASE
                    WHEN p.[Sales Cycle Status] IN (
                        'Customer Visit (20%)',
                        'Ask for Proposal (40%)',
                        'Negotiations (60%)',
                        'Documentation/Acceptance/Processing (80%)'
                    )
                    THEN 1
                    ELSE 0
                END
            ) AS ActivePipelines

        FROM Pipelines p

        JOIN Users u
            ON LTRIM(RTRIM(p.[Account Manager])) =
               LTRIM(RTRIM(u.EmployeeName))

        WHERE
            u.EmpID = ?
            OR u.ManagerID = ?
    """, (teamlead_id, teamlead_id))


    summary_row = cursor.fetchone()


    summary = {
        "TotalMRC": summary_row[0] or 0,
        "TotalOTC": summary_row[1] or 0,
        "TotalRevenue": summary_row[2] or 0,
        "ActivePipelines": summary_row[3] or 0
    }



    # =========================
    # TEAM MEMBER LIST
    # Team Lead + assigned EDOs
    # =========================

    cursor.execute("""
        SELECT
            EmpID,
            EmployeeName,
            FirstName,
            LastName

        FROM Users

        WHERE
            (
                EmpID = ?
                OR ManagerID = ?
            )
            AND IsActive = 1

        ORDER BY
            EmployeeName
    """, (teamlead_id, teamlead_id))


    edos = [
        {
            "EmpID": row[0],
            "FullName": row[1]
        }

        for row in cursor.fetchall()
    ]



    # =========================
    # REVENUE PER PERSON
    # Team Lead + assigned EDOs
    # Includes members with no pipelines
    # =========================

    cursor.execute("""
        SELECT
            u.FirstName AS FullName,
            COALESCE(SUM(p.[Total Project Revenue]), 0) AS Revenue

        FROM Users u

        LEFT JOIN Pipelines p
            ON LTRIM(RTRIM(p.[Account Manager])) =
               LTRIM(RTRIM(u.EmployeeName))

        WHERE
            (
                u.EmpID = ?
                OR u.ManagerID = ?
            )
            AND u.IsActive = 1

        GROUP BY
            u.EmpID,
            u.FirstName

        ORDER BY
            u.FirstName
    """, (teamlead_id, teamlead_id))


    edo_names = []
    edo_revenues = []

    for row in cursor.fetchall():
        edo_names.append(row[0])
        edo_revenues.append(row[1] or 0)
    # =========================
    # PIPELINE STATUS BY PERSON
    # Team Lead + assigned EDOs
    # Used by client-side chart filter
    # =========================

    cursor.execute("""
        SELECT
            u.EmpID,
            u.EmployeeName,
            p.[Sales Cycle Status],

            COUNT(p.PipelineID) AS StatusCount,

            COALESCE(
                SUM(p.[Total Project Revenue]),
                0
            ) AS TotalRevenue,

            COALESCE(
                SUM(p.[MRC]),
                0
            ) AS TotalMRC,

            COALESCE(
                SUM(p.[Project OTC]),
                0
            ) AS TotalOTC

        FROM Users u

        LEFT JOIN Pipelines p
            ON LTRIM(RTRIM(p.[Account Manager])) =
               LTRIM(RTRIM(u.EmployeeName))

        WHERE
            (
                u.EmpID = ?
                OR u.ManagerID = ?
            )
            AND u.IsActive = 1

        GROUP BY
            u.EmpID,
            u.EmployeeName,
            p.[Sales Cycle Status]

        ORDER BY
            u.EmployeeName,
            p.[Sales Cycle Status]
    """, (teamlead_id, teamlead_id))


    status_by_edo = {}

    for row in cursor.fetchall():

        emp_id = str(row[0])
        employee_name = row[1]
        status = row[2]

        count = row[3] or 0
        revenue = row[4] or 0
        mrc = row[5] or 0
        otc = row[6] or 0

        if emp_id not in status_by_edo:
            status_by_edo[emp_id] = {
                "name": employee_name,
                "statuses": {}
            }

        if status:
            status_by_edo[emp_id]["statuses"][status] = {
                "count": count,
                "revenue": revenue,
                "mrc": mrc,
                "otc": otc
            }


    all_statuses = {}

    for edo_data in status_by_edo.values():

        for status, metrics in edo_data["statuses"].items():

            if status not in all_statuses:
                all_statuses[status] = {
                    "count": 0,
                    "revenue": 0,
                    "mrc": 0,
                    "otc": 0
                }

            all_statuses[status]["count"] += metrics["count"]
            all_statuses[status]["revenue"] += metrics["revenue"]
            all_statuses[status]["mrc"] += metrics["mrc"]
            all_statuses[status]["otc"] += metrics["otc"]


    # =========================
    # PIPELINES
    # =========================

    pipelines = []


    # -------------------------
    # ALL TEAM PIPELINES
    # Team Lead + EDOs
    # -------------------------

    if selected_edo == "all":

        cursor.execute("""
            SELECT
                u.EmpID,
                p.[Account Manager],
                p.[Vertical],
                p.[Account Name],
                p.[Product],
                p.[Region],
                p.[MRC],
                p.[Contract Duration (Months)],
                p.[ARR],
                p.[Project OTC],
                p.[Total Project Revenue],
                p.[Estimated Closure Date],
                p.[Estimated Closure Month],
                p.[Sales Cycle Status],
                p.[Next Action]

            FROM Pipelines p

            JOIN Users u
                ON LTRIM(RTRIM(p.[Account Manager])) =
                   LTRIM(RTRIM(u.EmployeeName))

            WHERE
                (
                    u.EmpID = ?
                    OR u.ManagerID = ?
                )
                AND u.IsActive = 1

            ORDER BY
                p.[Account Manager],
                p.[Account Name]
        """, (teamlead_id, teamlead_id))


        pipelines = [
            {
                "EmpID": row[0],
                "AccountManager": row[1],
                "Vertical": row[2],
                "AccountName": row[3],
                "Product": row[4],
                "Region": row[5],
                "MRC": row[6],
                "ContractDuration": row[7],
                "ARR": row[8],
                "ProjectOTC": row[9],
                "TotalProjectRevenue": row[10],
                "EstimatedClosureDate": row[11],
                "EstimatedClosureMonth": row[12],
                "SalesCycleStatus": row[13],
                "NextAction": row[14]
            }

            for row in cursor.fetchall()
        ]


    # -------------------------
    # SPECIFIC TEAM MEMBER
    # -------------------------

    elif selected_edo:

        try:
            selected_edo = int(selected_edo)

        except ValueError:
            selected_edo = "all"


        if selected_edo != "all":

            selected_edo_name = next(
                (
                    edo["FullName"]

                    for edo in edos

                    if edo["EmpID"] == selected_edo
                ),
                None
            )


            if selected_edo_name:

                cursor.execute("""
                    SELECT
                        u.EmpID,
                        p.[Account Manager],
                        p.[Vertical],
                        p.[Account Name],
                        p.[Product],
                        p.[Region],
                        p.[MRC],
                        p.[Contract Duration (Months)],
                        p.[ARR],
                        p.[Project OTC],
                        p.[Total Project Revenue],
                        p.[Estimated Closure Date],
                        p.[Estimated Closure Month],
                        p.[Sales Cycle Status],
                        p.[Next Action]

                    FROM Pipelines p

                    JOIN Users u
                        ON LTRIM(RTRIM(p.[Account Manager])) =
                           LTRIM(RTRIM(u.EmployeeName))

                    WHERE
                        u.EmpID = ?
                        AND (
                            u.EmpID = ?
                            OR u.ManagerID = ?
                        )
                        AND u.IsActive = 1

                    ORDER BY
                        p.[Account Name]
                """, (
                    selected_edo,
                    teamlead_id,
                    teamlead_id
                ))


                pipelines = [
                    {
                        "EmpID": row[0],
                        "AccountManager": row[1],
                        "Vertical": row[2],
                        "AccountName": row[3],
                        "Product": row[4],
                        "Region": row[5],
                        "MRC": row[6],
                        "ContractDuration": row[7],
                        "ARR": row[8],
                        "ProjectOTC": row[9],
                        "TotalProjectRevenue": row[10],
                        "EstimatedClosureDate": row[11],
                        "EstimatedClosureMonth": row[12],
                        "SalesCycleStatus": row[13],
                        "NextAction": row[14]
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

        status_by_edo=status_by_edo,

        all_statuses=all_statuses
    )



@app.route("/add_pipeline", methods=["GET", "POST"])
def add_pipeline():

    # Allowed dropdown values
    verticals = [
        "Commercial",
        "FinTech",
        "Healthcare",
        "Manufacturing",
        "Telecom",
        "Others"
    ]

    products = [
        "0-365",
        "Boost",
        "Business Line",
        "Cloud",
        "CMT",
        "Device GSM",
        "Device MBB",
        "Digital Dukan",
        "FFM",
        "Fixed",
        "Group Data",
        "GSM",
        "M2M",
        "SaaS",
        "SIP",
        "Other"
    ]

    regions = [
        "Central",
        "CVM",
        "North",
        "South",
        "Others"
    ]

    statuses = [
        "Customer Visit (20%)",
        "Ask for Proposal (40%)",
        "Negotiations (60%)",
        "Documentation/Acceptance/Processing (80%)",
        "System Entry/Revenue Locked (100%)",
        "Lost to Competitor",
        "Retired - No Decision"
    ]

    # Logged-in Account Manager
    edo_name = (
        session.get("employee_name")
        or f"{session['first_name']} {session['last_name']}"
    )


    # =========================
    # GET
    # =========================

    if request.method == "GET":
        return render_template(
            "add_pipeline.html",
            edo_name=edo_name,
            verticals=verticals,
            products=products,
            regions=regions,
            statuses=statuses
        )


    # =========================
    # POST - FORM DATA
    # =========================

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


    # =========================
    # REQUIRED FIELD VALIDATION
    # =========================

    if not all([
        vertical,
        product,
        sales_cycle_status,
        account_name,
        region,
        closure_date
    ]):
        return "Please fill in all required fields.", 400


    # =========================
    # VALIDATE DROPDOWN VALUES
    # =========================

    if vertical not in verticals:
        return "Invalid Vertical selected.", 400

    if product not in products:
        return "Invalid Product selected.", 400

    if region not in regions:
        return "Invalid Region selected.", 400

    if sales_cycle_status not in statuses:
        return "Invalid Sales Cycle Status selected.", 400


    # =========================
    # CONVERT NUMBERS
    # =========================

    mrc = float(mrc) if mrc else None
    contract_duration = float(contract_duration) if contract_duration else None
    arr = float(arr) if arr else None
    project_otc = float(project_otc) if project_otc else None
    total_project_revenue = (
        float(total_project_revenue)
        if total_project_revenue
        else None
    )


    # =========================
    # CLOSURE DATE
    # =========================

    # Keep all three date columns populated for now
    closure_date_obj = datetime.strptime(
        closure_date,
        "%Y-%m-%d"
    )

    closure_day = closure_date_obj.day
    closure_month = closure_date_obj.strftime("%B")


    # =========================
    # ACCOUNT MANAGER
    # =========================

    account_manager = edo_name


    # =========================
    # INSERT INTO SQL SERVER
    # =========================

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
            EstimatedClosureDateFull,

            [Sales Cycle Status],
            [Account Manager],
            [Next Action]
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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

        closure_day,
        closure_month,
        closure_date,

        sales_cycle_status,
        account_manager,
        next_action
    )

    conn.commit()
    cursor.close()

    return redirect(url_for("my_pipelines"))



@app.route("/regional-manager")
def regional_manager_dashboard():

    # -------------------------
    # ACCESS CHECK
    # -------------------------

    if "user_id" not in session:
        return redirect(url_for("login"))

    if session.get("role") != "Regional Manager":
        return redirect(url_for("login"))


    regional_manager_id = session["user_id"]
    first_name = session.get("first_name", "")

    cursor = conn.cursor()


    # ========================================================
    # TEAM LEADS DIRECTLY UNDER THIS REGIONAL MANAGER
    # ========================================================

    cursor.execute("""
        SELECT
            EmpID,
            EmployeeName,
            FirstName,
            LastName

        FROM Users

        WHERE
            ManagerID = ?
            AND Role = 'Team Lead'
            AND IsActive = 1

        ORDER BY
            EmployeeName
    """, (regional_manager_id,))


    team_leads = [
        {
            "EmpID": row[0],
            "FullName": row[1]
        }
        for row in cursor.fetchall()
    ]


    # ========================================================
    # ALL INDIVIDUAL USERS IN THIS REGION
    #
    # Includes:
    # - Regional Manager
    # - Team Leads
    # - EDOs below those Team Leads
    # ========================================================

    cursor.execute("""
        WITH UserHierarchy AS (

            -- Start with the Regional Manager
            SELECT
                EmpID,
                EmployeeName,
                FirstName,
                LastName,
                Role,
                ManagerID

            FROM Users

            WHERE EmpID = ?


            UNION ALL


            -- Add everyone underneath them
            SELECT
                u.EmpID,
                u.EmployeeName,
                u.FirstName,
                u.LastName,
                u.Role,
                u.ManagerID

            FROM Users u

            INNER JOIN UserHierarchy h
                ON u.ManagerID = h.EmpID

            WHERE u.IsActive = 1
        )

        SELECT
            EmpID,
            EmployeeName,
            FirstName,
            LastName,
            Role

        FROM UserHierarchy

        ORDER BY
            FirstName,
            LastName
    """, (regional_manager_id,))


    region_users = [
        {
            "EmpID": row[0],
            "FullName": row[1],
            "Role": row[4]
        }
        for row in cursor.fetchall()
    ]


    # ========================================================
    # REGION SUMMARY
    #
    # Includes RM + Team Leads + EDOs
    # ========================================================

    cursor.execute("""
        WITH UserHierarchy AS (

            SELECT
                EmpID,
                EmployeeName,
                FirstName,
                LastName,
                Role,
                ManagerID

            FROM Users

            WHERE EmpID = ?


            UNION ALL


            SELECT
                u.EmpID,
                u.EmployeeName,
                u.FirstName,
                u.LastName,
                u.Role,
                u.ManagerID

            FROM Users u

            INNER JOIN UserHierarchy h
                ON u.ManagerID = h.EmpID

            WHERE u.IsActive = 1
        )

        SELECT
            COALESCE(SUM(p.[MRC]), 0),
            COALESCE(SUM(p.[Project OTC]), 0),
            COALESCE(SUM(p.[Total Project Revenue]), 0),
            COALESCE(
                SUM(
                    CASE
                        WHEN p.[Sales Cycle Status] IN (
                            'Customer Visit (20%)',
                            'Ask for Proposal (40%)',
                            'Negotiations (60%)',
                            'Documentation/Acceptance/Processing (80%)'
                        )
                        THEN 1
                        ELSE 0
                    END
                ),
                0
            ) AS ActivePipelines

        FROM UserHierarchy uh

        LEFT JOIN Pipelines p
            ON LTRIM(RTRIM(p.[Account Manager])) =
               LTRIM(RTRIM(uh.EmployeeName))
    """, (regional_manager_id,))


    summary_row = cursor.fetchone()

    summary = {
        "TotalMRC": summary_row[0] or 0,
        "TotalOTC": summary_row[1] or 0,
        "TotalRevenue": summary_row[2] or 0,
        "TotalPipelines": summary_row[3] or 0
    }


    # ========================================================
    # REVENUE BY TEAM
    #
    # Each Team Lead bar includes:
    # - Team Lead's own pipelines
    # - EDO pipelines underneath them
    # ========================================================

    cursor.execute("""
        WITH TeamHierarchy AS (

            -- Start from Team Leads under the RM
            SELECT
                u.EmpID,
                u.EmployeeName,
                u.FirstName,
                u.LastName,
                u.ManagerID,
                u.EmpID AS TeamLeadID,
                u.EmployeeName AS TeamLeadName

            FROM Users u

            WHERE
                u.ManagerID = ?
                AND u.Role = 'Team Lead'
                AND u.IsActive = 1


            UNION ALL


            -- Add users beneath those Team Leads
            SELECT
                u.EmpID,
                u.EmployeeName,
                u.FirstName,
                u.LastName,
                u.ManagerID,
                th.TeamLeadID,
                th.TeamLeadName

            FROM Users u

            INNER JOIN TeamHierarchy th
                ON u.ManagerID = th.EmpID

            WHERE u.IsActive = 1
        )


        SELECT
            th.TeamLeadID,
            th.TeamLeadName,
            COALESCE(SUM(p.[Total Project Revenue]), 0)

        FROM TeamHierarchy th

        LEFT JOIN Pipelines p
            ON LTRIM(RTRIM(p.[Account Manager])) =
               LTRIM(RTRIM(th.EmployeeName))

        GROUP BY
            th.TeamLeadID,
            th.TeamLeadName

        ORDER BY
            th.TeamLeadName
    """, (regional_manager_id,))


    team_names = []
    team_revenues = []


    for row in cursor.fetchall():

        team_names.append(row[1])

        team_revenues.append(
            row[2] or 0
        )
    # ========================================================
    # REGION PIPELINE STATUS BY PERSON
    #
    # Filter options:
    # - Team Leads
    # - EDOs
    #
    # Used by client-side chart filter so the page does NOT
    # reload when a person is selected.
    # ========================================================

    status_users = [
        user
        for user in region_users
        if user["Role"] in ["Team Lead", "EDO"]
    ]


    cursor.execute("""
        WITH UserHierarchy AS (

            SELECT
                EmpID,
                EmployeeName,
                Role,
                ManagerID

            FROM Users

            WHERE EmpID = ?


            UNION ALL


            SELECT
                u.EmpID,
                u.EmployeeName,
                u.Role,
                u.ManagerID

            FROM Users u

            INNER JOIN UserHierarchy h
                ON u.ManagerID = h.EmpID

            WHERE u.IsActive = 1
        )

        SELECT
            uh.EmpID,
            uh.EmployeeName,
            p.[Sales Cycle Status],

            COUNT(p.PipelineID) AS StatusCount,

            COALESCE(
                SUM(p.[Total Project Revenue]),
                0
            ) AS TotalRevenue,

            COALESCE(
                SUM(p.[MRC]),
                0
            ) AS TotalMRC,

            COALESCE(
                SUM(p.[Project OTC]),
                0
            ) AS TotalOTC

        FROM UserHierarchy uh

        LEFT JOIN Pipelines p
            ON LTRIM(RTRIM(p.[Account Manager])) =
               LTRIM(RTRIM(uh.EmployeeName))

        WHERE
            uh.Role IN ('Team Lead', 'EDO')

        GROUP BY
            uh.EmpID,
            uh.EmployeeName,
            p.[Sales Cycle Status]

        ORDER BY
            uh.EmployeeName,
            p.[Sales Cycle Status]
    """, (regional_manager_id,))


    status_by_user = {}

    for row in cursor.fetchall():

        emp_id = str(row[0])
        employee_name = row[1]
        status = row[2]
        count = row[3] or 0
        revenue = row[4] or 0
        mrc = row[5] or 0
        otc = row[6] or 0

        if emp_id not in status_by_user:
            status_by_user[emp_id] = {
                "name": employee_name,
                "statuses": {}
            }

        if status:
            status_by_user[emp_id]["statuses"][status] = {
                "count": count,
                "revenue": revenue,
                "mrc": mrc,
                "otc": otc
            }


    all_statuses = {}

    for user_data in status_by_user.values():

        for status, metrics in user_data["statuses"].items():

            if status not in all_statuses:
                all_statuses[status] = {
                    "count": 0,
                    "revenue": 0,
                    "mrc": 0,
                    "otc": 0
                }

            all_statuses[status]["count"] += metrics["count"]
            all_statuses[status]["revenue"] += metrics["revenue"]
            all_statuses[status]["mrc"] += metrics["mrc"]
            all_statuses[status]["otc"] += metrics["otc"]


    # ========================================================
    # ALL REGION PIPELINES
    #
    # Includes:
    # - RM
    # - Team Leads
    # - EDOs
    #
    # IMPORTANT:
    # EmpID is now included so HTML can filter by individual.
    # ========================================================

    cursor.execute("""
        WITH TeamHierarchy AS (

            -- Team Leads directly under RM
            SELECT
                u.EmpID,
                u.EmployeeName,
                u.FirstName,
                u.LastName,
                u.Role,
                u.ManagerID,

                u.EmpID AS TeamLeadID,

                u.EmployeeName
                    AS TeamLeadName

            FROM Users u

            WHERE
                u.ManagerID = ?
                AND u.Role = 'Team Lead'
                AND u.IsActive = 1


            UNION ALL


            -- Everyone underneath each Team Lead
            SELECT
                u.EmpID,
                u.EmployeeName,
                u.FirstName,
                u.LastName,
                u.Role,
                u.ManagerID,

                th.TeamLeadID,
                th.TeamLeadName

            FROM Users u

            INNER JOIN TeamHierarchy th
                ON u.ManagerID = th.EmpID

            WHERE u.IsActive = 1
        ),


        RegionUsers AS (

            -- Regional Manager
            SELECT
                u.EmpID,
                u.EmployeeName,
                u.FirstName,
                u.LastName,

                NULL AS TeamLeadID,

                'Regional Manager'
                    AS TeamName

            FROM Users u

            WHERE u.EmpID = ?


            UNION ALL


            -- Team Leads + EDOs
            SELECT
                th.EmpID,
                th.EmployeeName,
                th.FirstName,
                th.LastName,

                th.TeamLeadID,

                th.TeamLeadName
                    AS TeamName

            FROM TeamHierarchy th
        )


        SELECT
            ru.EmpID,
            p.[Account Manager],
            ru.TeamName,
            ru.TeamLeadID,
            p.[Vertical],
            p.[Account Name],
            p.[Product],
            p.[Region],
            p.[MRC],
            p.[Contract Duration (Months)],
            p.[ARR],
            p.[Project OTC],
            p.[Total Project Revenue],
            p.[Estimated Closure Date],
            p.[Estimated Closure Month],
            p.[Sales Cycle Status],
            p.[Next Action]

        FROM Pipelines p

        INNER JOIN RegionUsers ru
            ON LTRIM(RTRIM(p.[Account Manager])) =
               LTRIM(RTRIM(ru.EmployeeName))

        ORDER BY
            p.[Account Manager],
            p.[Account Name]
    """, (
        regional_manager_id,
        regional_manager_id
    ))


    pipelines = [
        {
            "EmpID": row[0],
            "AccountManager": row[1],
            "TeamName": row[2],
            "TeamLeadID": row[3],
            "Vertical": row[4],
            "AccountName": row[5],
            "Product": row[6],
            "Region": row[7],
            "MRC": row[8],
            "ContractDuration": row[9],
            "ARR": row[10],
            "ProjectOTC": row[11],
            "TotalProjectRevenue": row[12],
            "EstimatedClosureDate": row[13],
            "EstimatedClosureMonth": row[14],
            "SalesCycleStatus": row[15],
            "NextAction": row[16]
        }
        for row in cursor.fetchall()
    ]


    # ========================================================
    # RENDER DASHBOARD
    # ========================================================

    return render_template(
        "regional_manager.html",

        first_name=first_name,

        summary=summary,

        team_leads=team_leads,

        # NEW:
        # Used by the individual dropdown
        region_users=region_users,

        team_names=team_names,
        team_revenues=team_revenues,
        status_users=status_users,

        status_by_user=status_by_user,
        all_statuses=all_statuses,

        pipelines=pipelines
    )


# ============================================================
# REGIONAL MANAGER -> TEAM DRILL-DOWN
# ============================================================

@app.route("/regional-manager/team/<int:teamlead_id>")
def regional_manager_team_dashboard(teamlead_id):

    # -------------------------
    # ACCESS CHECK
    # -------------------------

    if "user_id" not in session:
        return redirect(url_for("login"))

    role = (session.get("role") or "").strip()

    executive_roles = app.config.get(
        "EXECUTIVE_DASHBOARD_ROLES",
        set()
    )

    allowed_roles = {
        "Regional Manager",
        "Regional Head"
    } | executive_roles

    if role not in allowed_roles:
        return redirect(url_for("login"))


    viewer_id = session["user_id"]
    viewer_first_name = session.get("first_name", "")

    cursor = conn.cursor()

    # ========================================================
    # CHECK THAT THIS USER CAN VIEW THIS TEAM
    # ========================================================

    executive_roles = app.config.get(
        "EXECUTIVE_DASHBOARD_ROLES",
        set()
    )


    if role == "Regional Manager":

        cursor.execute("""
            SELECT
                EmpID,
                EmployeeName,
                FirstName,
                LastName

            FROM Users

            WHERE
                EmpID = ?
                AND ManagerID = ?
                AND Role = 'Team Lead'
                AND IsActive = 1
        """, (teamlead_id, viewer_id))


    elif role == "Regional Head":

        cursor.execute("""
            SELECT
                tl.EmpID,
                tl.EmployeeName,
                tl.FirstName,
                tl.LastName

            FROM Users tl

            INNER JOIN Users rm
                ON tl.ManagerID = rm.EmpID

            WHERE
                tl.EmpID = ?
                AND tl.Role = 'Team Lead'
                AND tl.IsActive = 1

                AND rm.ManagerID = ?
                AND rm.Role = 'Regional Manager'
                AND rm.IsActive = 1
        """, (teamlead_id, viewer_id))


    elif role in executive_roles:

        cursor.execute("""
            SELECT
                EmpID,
                EmployeeName,
                FirstName,
                LastName

            FROM Users

            WHERE
                EmpID = ?
                AND Role = 'Team Lead'
                AND IsActive = 1
        """, (teamlead_id,))


    else:

        return redirect(
            url_for("login")
        )


    teamlead_row = cursor.fetchone()


    if not teamlead_row:

        if role == "Regional Head":

            return redirect(
                url_for(
                    "regional_head_dashboard"
                )
            )


        elif role in executive_roles:

            return redirect(
                url_for(
                    "executive_dashboard"
                )
            )


        return redirect(
            url_for(
                "regional_manager_dashboard"
            )
        )


    teamlead_name = teamlead_row[1]


    # ========================================================
    # TEAM MEMBERS
    # Team Lead + assigned EDOs
    # ========================================================

    cursor.execute("""
        SELECT
            EmpID,
            EmployeeName,
            FirstName,
            LastName,
            Role

        FROM Users

        WHERE
            (
                EmpID = ?
                OR ManagerID = ?
            )
            AND IsActive = 1

        ORDER BY
            EmployeeName
    """, (teamlead_id, teamlead_id))


    team_members = [
        {
            "EmpID": row[0],
            "FullName": row[1],
            "Role": row[4]
        }
        for row in cursor.fetchall()
    ]


    # ========================================================
    # TEAM SUMMARY
    # ========================================================

    cursor.execute("""
        SELECT
            COALESCE(SUM(p.[MRC]), 0),
            COALESCE(SUM(p.[Project OTC]), 0),
            COALESCE(SUM(p.[Total Project Revenue]), 0),
            COALESCE(
                SUM(
                    CASE
                        WHEN p.[Sales Cycle Status] IN (
                            'Customer Visit (20%)',
                            'Ask for Proposal (40%)',
                            'Negotiations (60%)',
                            'Documentation/Acceptance/Processing (80%)'
                        )
                        THEN 1
                        ELSE 0
                    END
                ),
                0
            ) AS ActivePipelines

        FROM Users u

        LEFT JOIN Pipelines p
            ON LTRIM(RTRIM(p.[Account Manager])) =
               LTRIM(RTRIM(u.EmployeeName))

        WHERE
            u.EmpID = ?
            OR u.ManagerID = ?
    """, (teamlead_id, teamlead_id))


    summary_row = cursor.fetchone()

    summary = {
        "TotalMRC": summary_row[0] or 0,
        "TotalOTC": summary_row[1] or 0,
        "TotalRevenue": summary_row[2] or 0,
        "ActivePipelines": summary_row[3] or 0
    }


    # ========================================================
    # REVENUE BY TEAM MEMBER
    # ========================================================

    cursor.execute("""
        SELECT
            u.FirstName AS FullName,
            COALESCE(SUM(p.[Total Project Revenue]), 0)

        FROM Users u

        LEFT JOIN Pipelines p
            ON LTRIM(RTRIM(p.[Account Manager])) =
               LTRIM(RTRIM(u.EmployeeName))

        WHERE
            u.EmpID = ?
            OR u.ManagerID = ?

        GROUP BY
            u.EmpID,
            u.FirstName

        ORDER BY
            u.FirstName
    """, (teamlead_id, teamlead_id))


    member_names = []
    member_revenues = []

    for row in cursor.fetchall():
        member_names.append(row[0])
        member_revenues.append(row[1] or 0)


    # ========================================================
    # TEAM PIPELINE STATUS BY PERSON
    # Team Lead + assigned EDOs
    # Used by client-side chart filter
    # ========================================================

    cursor.execute("""
        SELECT
            u.EmpID,
            u.EmployeeName,
            p.[Sales Cycle Status],

            COUNT(p.PipelineID) AS StatusCount,

            COALESCE(
                SUM(p.[Total Project Revenue]),
                0
            ) AS TotalRevenue,

            COALESCE(
                SUM(p.[MRC]),
                0
            ) AS TotalMRC,

            COALESCE(
                SUM(p.[Project OTC]),
                0
            ) AS TotalOTC

        FROM Users u

        LEFT JOIN Pipelines p
            ON LTRIM(RTRIM(p.[Account Manager])) =
               LTRIM(RTRIM(u.EmployeeName))

        WHERE
            (
                u.EmpID = ?
                OR u.ManagerID = ?
            )
            AND u.IsActive = 1

        GROUP BY
            u.EmpID,
            u.EmployeeName,
            p.[Sales Cycle Status]

        ORDER BY
            u.EmployeeName,
            p.[Sales Cycle Status]
    """, (teamlead_id, teamlead_id))


    status_by_user = {}

    for row in cursor.fetchall():

        emp_id = str(row[0])
        employee_name = row[1]
        status = row[2]
        count = row[3] or 0
        revenue = row[4] or 0
        mrc = row[5] or 0
        otc = row[6] or 0

        if emp_id not in status_by_user:
            status_by_user[emp_id] = {
                "name": employee_name,
                "statuses": {}
            }

        if status:
            status_by_user[emp_id]["statuses"][status] = {
                "count": count,
                "revenue": revenue,
                "mrc": mrc,
                "otc": otc
            }


    all_statuses = {}

    for user_data in status_by_user.values():

        for status, metrics in user_data["statuses"].items():

            if status not in all_statuses:
                all_statuses[status] = {
                    "count": 0,
                    "revenue": 0,
                    "mrc": 0,
                    "otc": 0
                }

            all_statuses[status]["count"] += metrics["count"]
            all_statuses[status]["revenue"] += metrics["revenue"]
            all_statuses[status]["mrc"] += metrics["mrc"]
            all_statuses[status]["otc"] += metrics["otc"]


    # ========================================================
    # TEAM PIPELINES
    # ========================================================

    cursor.execute("""
        SELECT
            u.EmpID,
            p.[Account Manager],
            p.[Vertical],
            p.[Account Name],
            p.[Product],
            p.[Region],
            p.[MRC],
            p.[Contract Duration (Months)],
            p.[ARR],
            p.[Project OTC],
            p.[Total Project Revenue],
            p.[Estimated Closure Date],
            p.[Estimated Closure Month],
            p.[Sales Cycle Status],
            p.[Next Action]

        FROM Pipelines p

        INNER JOIN Users u
            ON LTRIM(RTRIM(p.[Account Manager])) =
               LTRIM(RTRIM(u.EmployeeName))

        WHERE
            u.EmpID = ?
            OR u.ManagerID = ?

        ORDER BY
            p.[Account Manager],
            p.[Account Name]
    """, (teamlead_id, teamlead_id))


    pipelines = [
        {
            "EmpID": row[0],
            "AccountManager": row[1],
            "Vertical": row[2],
            "AccountName": row[3],
            "Product": row[4],
            "Region": row[5],
            "MRC": row[6],
            "ContractDuration": row[7],
            "ARR": row[8],
            "ProjectOTC": row[9],
            "TotalProjectRevenue": row[10],
            "EstimatedClosureDate": row[11],
            "EstimatedClosureMonth": row[12],
            "SalesCycleStatus": row[13],
            "NextAction": row[14]
        }
        for row in cursor.fetchall()
    ]


    return render_template(
        "regional_manager_team.html",

        viewer_first_name=viewer_first_name,
        viewer_role=role,

        teamlead_name=teamlead_name,

        team_members=team_members,

        summary=summary,

        member_names=member_names,
        member_revenues=member_revenues,

        status_by_user=status_by_user,
        all_statuses=all_statuses,

        pipelines=pipelines
    )






# ============================================================
# HEAD DASHBOARD
# ============================================================

@app.route("/regional-head")
def regional_head_dashboard():

    # -------------------------
    # ACCESS CHECK
    # -------------------------

    if "user_id" not in session:
        return redirect(url_for("login"))

    if session.get("role") != "Regional Head":
        return redirect(url_for("login"))

    regional_head_id = session["user_id"]
    head_id = session["user_id"]
    first_name = session.get("first_name", "")

    cursor = conn.cursor()


    # ========================================================
    # REGIONAL MANAGERS DIRECTLY UNDER THIS HEAD
    # ========================================================

    cursor.execute("""
        SELECT
            EmpID,
            EmployeeName

        FROM Users

        WHERE
            ManagerID = ?
            AND Role = 'Regional Manager'
            AND IsActive = 1

        ORDER BY
            EmployeeName
    """, (head_id,))


    regional_managers = [
        {
            "EmpID": row[0],
            "FullName": row[1]
        }

        for row in cursor.fetchall()
    ]


    # ========================================================
    # TEAM LEADS
    #
    # All Team Leads underneath Regional Managers
    # belonging to this Head.
    # ========================================================

    cursor.execute("""
        SELECT
            tl.EmpID,
            tl.EmployeeName,

            rm.EmpID AS RegionalManagerID,
            rm.EmployeeName AS RegionalManagerName

        FROM Users rm

        INNER JOIN Users tl
            ON tl.ManagerID = rm.EmpID

        WHERE
            rm.ManagerID = ?
            AND rm.Role = 'Regional Manager'
            AND rm.IsActive = 1

            AND tl.Role = 'Team Lead'
            AND tl.IsActive = 1

        ORDER BY
            rm.EmployeeName,
            tl.EmployeeName
    """, (head_id,))


    team_leads = [
        {
            "EmpID": row[0],
            "FullName": row[1],

            "RegionalManagerID": row[2],
            "RegionalManagerName": row[3]
        }

        for row in cursor.fetchall()
    ]


    # ========================================================
    # ALL USERS UNDER HEAD
    #
    # Includes:
    # - Head
    # - Regional Managers
    # - Team Leads
    # - EDOs
    # ========================================================

    cursor.execute("""
        WITH UserHierarchy AS (

            -- Start with Head
            SELECT
                EmpID,
                EmployeeName,
                FirstName,
                LastName,
                Role,
                ManagerID

            FROM Users

            WHERE EmpID = ?


            UNION ALL


            -- Everyone below the current person
            SELECT
                u.EmpID,
                u.EmployeeName,
                u.FirstName,
                u.LastName,
                u.Role,
                u.ManagerID

            FROM Users u

            INNER JOIN UserHierarchy h
                ON u.ManagerID = h.EmpID

            WHERE u.IsActive = 1
        )

        SELECT
            EmpID,
            EmployeeName,
            Role

        FROM UserHierarchy

        ORDER BY
            EmployeeName
    """, (head_id,))


    head_users = [
        {
            "EmpID": row[0],
            "FullName": row[1],
            "Role": row[2]
        }

        for row in cursor.fetchall()
    ]


    # ========================================================
    # HEAD SUMMARY
    #
    # Head + RMs + TLs + EDOs
    # ========================================================

    cursor.execute("""
        WITH UserHierarchy AS (

            SELECT
                EmpID,
                EmployeeName,
                Role,
                ManagerID

            FROM Users

            WHERE EmpID = ?


            UNION ALL


            SELECT
                u.EmpID,
                u.EmployeeName,
                u.Role,
                u.ManagerID

            FROM Users u

            INNER JOIN UserHierarchy h
                ON u.ManagerID = h.EmpID

            WHERE u.IsActive = 1
        )

        SELECT
            COALESCE(SUM(p.[MRC]), 0),
            COALESCE(SUM(p.[Project OTC]), 0),
            COALESCE(SUM(p.[Total Project Revenue]), 0),
            COALESCE(
                SUM(
                    CASE
                        WHEN p.[Sales Cycle Status] IN (
                            'Customer Visit (20%)',
                            'Ask for Proposal (40%)',
                            'Negotiations (60%)',
                            'Documentation/Acceptance/Processing (80%)'
                        )
                        THEN 1
                        ELSE 0
                    END
                ),
                0
            ) AS ActivePipelines

        FROM UserHierarchy uh

        LEFT JOIN Pipelines p
            ON LTRIM(RTRIM(p.[Account Manager])) =
               LTRIM(RTRIM(uh.EmployeeName))

    """, (head_id,))


    summary_row = cursor.fetchone()

    summary = {
        "TotalMRC": summary_row[0] or 0,
        "TotalOTC": summary_row[1] or 0,
        "TotalRevenue": summary_row[2] or 0,
        "ActivePipelines": summary_row[3] or 0
    }


    # ========================================================
    # REVENUE BY TEAM
    #
    # One bar per Team Lead.
    #
    # Includes:
    # - Team Lead's own pipelines
    # - EDO pipelines underneath Team Lead
    #
    # Team Leads with no pipelines still appear as 0.
    # ========================================================

    cursor.execute("""
        WITH TeamHierarchy AS (

            -- Start with Team Leads under this Head's RMs
            SELECT
                tl.EmpID,
                tl.EmployeeName,
                tl.ManagerID,

                tl.EmpID AS TeamLeadID,
                tl.EmployeeName AS TeamLeadName,

                rm.EmpID AS RegionalManagerID,
                rm.EmployeeName AS RegionalManagerName

            FROM Users rm

            INNER JOIN Users tl
                ON tl.ManagerID = rm.EmpID

            WHERE
                rm.ManagerID = ?
                AND rm.Role = 'Regional Manager'
                AND rm.IsActive = 1

                AND tl.Role = 'Team Lead'
                AND tl.IsActive = 1


            UNION ALL


            -- Add EDOs underneath each Team Lead
            SELECT
                u.EmpID,
                u.EmployeeName,
                u.ManagerID,

                th.TeamLeadID,
                th.TeamLeadName,

                th.RegionalManagerID,
                th.RegionalManagerName

            FROM Users u

            INNER JOIN TeamHierarchy th
                ON u.ManagerID = th.EmpID

            WHERE u.IsActive = 1
        )

        SELECT
            th.TeamLeadID,
            th.TeamLeadName,
            th.RegionalManagerID,
            th.RegionalManagerName,

            COALESCE(
                SUM(p.[Total Project Revenue]),
                0
            ) AS TeamRevenue

        FROM TeamHierarchy th

        LEFT JOIN Pipelines p
            ON LTRIM(RTRIM(p.[Account Manager])) =
               LTRIM(RTRIM(th.EmployeeName))

        GROUP BY
            th.TeamLeadID,
            th.TeamLeadName,
            th.RegionalManagerID,
            th.RegionalManagerName

        ORDER BY
            th.TeamLeadName

    """, (head_id,))


    team_names = []
    team_revenues = []

    for row in cursor.fetchall():

        team_names.append(row[1])
        team_revenues.append(row[4] or 0)
    # ========================================================
    # PIPELINE STATUS BY PERSON
    #
    # Regional Head view:
    # - All Team Leads
    # - All EDOs
    #
    # Used by client-side chart filter so selecting a person
    # updates only the pie chart and does not reload the page.
    # ========================================================

    status_users = [
        user
        for user in head_users
        if user["Role"] in ["Team Lead", "EDO"]
    ]


    cursor.execute("""
        WITH UserHierarchy AS (

            SELECT
                EmpID,
                EmployeeName,
                Role,
                ManagerID

            FROM Users

            WHERE EmpID = ?


            UNION ALL


            SELECT
                u.EmpID,
                u.EmployeeName,
                u.Role,
                u.ManagerID

            FROM Users u

            INNER JOIN UserHierarchy h
                ON u.ManagerID = h.EmpID

            WHERE u.IsActive = 1
        )

        SELECT
            uh.EmpID,
            uh.EmployeeName,
            p.[Sales Cycle Status],

            COUNT(p.PipelineID) AS StatusCount,

            COALESCE(
                SUM(p.[Total Project Revenue]),
                0
            ) AS TotalRevenue,

            COALESCE(
                SUM(p.[MRC]),
                0
            ) AS TotalMRC,

            COALESCE(
                SUM(p.[Project OTC]),
                0
            ) AS TotalOTC

        FROM UserHierarchy uh

        LEFT JOIN Pipelines p
            ON LTRIM(RTRIM(p.[Account Manager])) =
               LTRIM(RTRIM(uh.EmployeeName))

        WHERE
            uh.Role IN ('Team Lead', 'EDO')

        GROUP BY
            uh.EmpID,
            uh.EmployeeName,
            p.[Sales Cycle Status]

        ORDER BY
            uh.EmployeeName,
            p.[Sales Cycle Status]
    """, (head_id,))


    status_by_user = {}

    for row in cursor.fetchall():

        emp_id = str(row[0])
        employee_name = row[1]
        status = row[2]
        count = row[3] or 0
        revenue = row[4] or 0
        mrc = row[5] or 0
        otc = row[6] or 0

        if emp_id not in status_by_user:
            status_by_user[emp_id] = {
                "name": employee_name,
                "statuses": {}
            }

        if status:
            status_by_user[emp_id]["statuses"][status] = {
                "count": count,
                "revenue": revenue,
                "mrc": mrc,
                "otc": otc
            }


    all_statuses = {}

    for user_data in status_by_user.values():

        for status, metrics in user_data["statuses"].items():

            if status not in all_statuses:
                all_statuses[status] = {
                    "count": 0,
                    "revenue": 0,
                    "mrc": 0,
                    "otc": 0
                }

            all_statuses[status]["count"] += metrics["count"]
            all_statuses[status]["revenue"] += metrics["revenue"]
            all_statuses[status]["mrc"] += metrics["mrc"]
            all_statuses[status]["otc"] += metrics["otc"]


    # ========================================================
    # ALL PIPELINES
    #
    # Also determines which Regional Manager and Team
    # each pipeline belongs to.
    # ========================================================
        cursor.execute("""
            WITH Hierarchy AS (

                -- Regional Managers
                SELECT
                    rm.EmpID,
                    rm.EmployeeName,
                    rm.Role,
                    rm.ManagerID,

                    rm.EmpID AS RegionalManagerID,
                    rm.EmployeeName AS RegionalManagerName,

                    CAST(NULL AS INT) AS TeamLeadID,
                    CAST(NULL AS VARCHAR(255)) AS TeamLeadName

                FROM Users rm

                WHERE
                    rm.ManagerID = ?
                    AND rm.Role = 'Regional Manager'
                    AND rm.IsActive = 1


                UNION ALL


                -- Everyone underneath them
                SELECT
                    u.EmpID,
                    u.EmployeeName,
                    u.Role,
                    u.ManagerID,

                    h.RegionalManagerID,
                    h.RegionalManagerName,

                    CASE
                        WHEN u.Role = 'Team Lead'
                            THEN u.EmpID
                        ELSE h.TeamLeadID
                    END AS TeamLeadID,

                    CASE
                        WHEN u.Role = 'Team Lead'
                            THEN u.EmployeeName
                        ELSE h.TeamLeadName
                    END AS TeamLeadName

                FROM Users u

                INNER JOIN Hierarchy h
                    ON u.ManagerID = h.EmpID

                WHERE u.IsActive = 1
            ),


            RegionalHeadUsers AS (

                -- Regional Head's own pipelines
                SELECT
                    u.EmpID,
                    u.EmployeeName,

                    CAST(NULL AS INT) AS RegionalManagerID,
                    CAST(NULL AS VARCHAR(255)) AS RegionalManagerName,

                    CAST(NULL AS INT) AS TeamLeadID,
                    CAST(NULL AS VARCHAR(255)) AS TeamLeadName

                FROM Users u

                WHERE u.EmpID = ?


                UNION ALL


                -- Everyone below the Regional Head
                SELECT
                    h.EmpID,
                    h.EmployeeName,

                    h.RegionalManagerID,
                    h.RegionalManagerName,

                    h.TeamLeadID,
                    h.TeamLeadName

                FROM Hierarchy h
            )


            SELECT
                rhu.EmpID,

                p.[Account Manager],

                rhu.RegionalManagerID,
                rhu.RegionalManagerName,

                rhu.TeamLeadID,
                rhu.TeamLeadName,

                p.[Vertical],
                p.[Account Name],
                p.[Product],
                p.[Region],
                p.[MRC],
                p.[Contract Duration (Months)],
                p.[ARR],
                p.[Project OTC],
                p.[Total Project Revenue],
                p.[Estimated Closure Date],
                p.[Estimated Closure Month],
                p.[Sales Cycle Status],
                p.[Next Action]

            FROM Pipelines p

            INNER JOIN RegionalHeadUsers rhu
                ON LTRIM(RTRIM(p.[Account Manager])) =
                LTRIM(RTRIM(rhu.EmployeeName))

            ORDER BY
                p.[Account Manager],
                p.[Account Name]

        """, (
            regional_head_id,
            regional_head_id
        ))

        pipelines = [
            {
                "EmpID": row[0],

                "AccountManager": row[1],

                "RegionalManagerID": row[2],
                "RegionalManagerName": row[3],

                "TeamLeadID": row[4],
                "TeamLeadName": row[5],

                "Vertical": row[6],
                "AccountName": row[7],
                "Product": row[8],
                "Region": row[9],
                "MRC": row[10],
                "ContractDuration": row[11],
                "ARR": row[12],
                "ProjectOTC": row[13],
                "TotalProjectRevenue": row[14],
                "EstimatedClosureDate": row[15],
                "EstimatedClosureMonth": row[16],
                "SalesCycleStatus": row[17],
                "NextAction": row[18]
            }

            for row in cursor.fetchall()
        ]


    cursor.execute("""
        WITH UserHierarchy AS (

            SELECT
                EmpID,
                EmployeeName,
                Role,
                ManagerID

            FROM Users

            WHERE EmpID = ?


            UNION ALL


            SELECT
                u.EmpID,
                u.EmployeeName,
                u.Role,
                u.ManagerID

            FROM Users u

            INNER JOIN UserHierarchy h
                ON u.ManagerID = h.EmpID

            WHERE u.IsActive = 1
        ),

        PipelineDates AS (

            SELECT
                p.PipelineID,
                p.[Account Name],
                p.[Account Manager],
                p.[Sales Cycle Status],
                p.[Next Action],

                DATEFROMPARTS(
                    YEAR(GETDATE()),

                    CASE p.[Estimated Closure Month]
                        WHEN 'January' THEN 1
                        WHEN 'February' THEN 2
                        WHEN 'March' THEN 3
                        WHEN 'April' THEN 4
                        WHEN 'May' THEN 5
                        WHEN 'June' THEN 6
                        WHEN 'July' THEN 7
                        WHEN 'August' THEN 8
                        WHEN 'September' THEN 9
                        WHEN 'October' THEN 10
                        WHEN 'November' THEN 11
                        WHEN 'December' THEN 12
                    END,

                    TRY_CAST(
                        p.[Estimated Closure Date]
                        AS INT
                    )
                ) AS ClosureDate

            FROM Pipelines p

            INNER JOIN UserHierarchy uh
                ON LTRIM(RTRIM(p.[Account Manager])) =
                LTRIM(RTRIM(uh.EmployeeName))

            WHERE
                p.[Estimated Closure Date] IS NOT NULL
                AND p.[Estimated Closure Month] IS NOT NULL
        )

        SELECT
            PipelineID,
            [Account Name],
            [Account Manager],
            [Sales Cycle Status],
            [Next Action],
            ClosureDate,
            DATEDIFF(
                DAY,
                CAST(GETDATE() AS DATE),
                ClosureDate
            ) AS DaysRemaining

        FROM PipelineDates

        WHERE
            ClosureDate >= CAST(GETDATE() AS DATE)

            AND ClosureDate <= DATEADD(
                DAY,
                7,
                CAST(GETDATE() AS DATE)
            )

        ORDER BY
            ClosureDate ASC

    """, (regional_head_id,))

    upcoming_deadlines = [
        {
            "PipelineID": row[0],
            "AccountName": row[1],
            "AccountManager": row[2],
            "Status": row[3],
            "NextAction": row[4],
            "ClosureDate": row[5],
            "DaysRemaining": row[6]
        }

        for row in cursor.fetchall()
    ]

    # ========================================================
    # OVERDUE PIPELINES
    # ========================================================

    cursor.execute("""
        WITH UserHierarchy AS (

            -- Start with the Regional Head
            SELECT
                EmpID,
                EmployeeName,
                Role,
                ManagerID

            FROM Users

            WHERE
                EmpID = ?
                AND IsActive = 1


            UNION ALL


            -- Everyone underneath the Regional Head
            SELECT
                u.EmpID,
                u.EmployeeName,
                u.Role,
                u.ManagerID

            FROM Users u

            INNER JOIN UserHierarchy h
                ON u.ManagerID = h.EmpID

            WHERE
                u.IsActive = 1
        )


        SELECT
            p.PipelineID,
            p.[Account Name],
            p.[Account Manager],
            p.[Product],
            p.EstimatedClosureDateFull,
            p.[Sales Cycle Status],

            DATEDIFF(
                DAY,
                p.EstimatedClosureDateFull,
                CAST(GETDATE() AS DATE)
            ) AS DaysOverdue

        FROM Pipelines p

        INNER JOIN UserHierarchy uh
            ON LTRIM(RTRIM(p.[Account Manager])) =
               LTRIM(RTRIM(uh.EmployeeName))

        WHERE
            p.EstimatedClosureDateFull IS NOT NULL

            AND p.EstimatedClosureDateFull <
                CAST(GETDATE() AS DATE)

            AND p.[Sales Cycle Status] IN (
                'Customer Visit (20%)',
                'Ask for Proposal (40%)',
                'Negotiations (60%)',
                'Documentation/Acceptance/Processing (80%)'
            )

        ORDER BY
            p.EstimatedClosureDateFull ASC,
            p.[Account Name] ASC

    """, (regional_head_id,))


    overdue_pipelines = [
        {
            "PipelineID": row[0],
            "AccountName": row[1],
            "AccountManager": row[2],
            "Product": row[3],
            "ClosureDate": row[4],
            "Status": row[5],
            "DaysOverdue": row[6]
        }

        for row in cursor.fetchall()
    ]


    # ========================================================
    # EDIT HISTORY
    # ========================================================

    history = []
    history_users = []

    history_cursor = conn.cursor()

    history_cursor.execute("""
        SELECT
            HistoryID,
            [Account Name],
            FieldName,
            OldValue,
            NewValue,
            EditedBy,
            EditedOn
        FROM dbo.History
        ORDER BY EditedOn DESC
    """)

    history = [
        {
            "HistoryID": row[0],
            "AccountName": row[1],
            "FieldName": row[2],
            "OldValue": row[3],
            "NewValue": row[4],
            "EditedBy": row[5],
            "EditedOn": row[6]
        }
        for row in history_cursor.fetchall()
    ]


    history_cursor.execute("""
        SELECT DISTINCT
            EditedBy
        FROM dbo.History
        WHERE
            EditedBy IS NOT NULL
            AND LTRIM(RTRIM(EditedBy)) <> ''
        ORDER BY EditedBy
    """)

    history_users = [
        row[0]
        for row in history_cursor.fetchall()
    ]

    history_cursor.close()
    # ========================================================
    # RENDER
    # ========================================================

    return render_template(
        "regional_head.html",

        first_name=first_name,
        summary=summary,

        regional_managers=regional_managers,
        team_leads=team_leads,

        head_users=head_users,

        team_names=team_names,
        team_revenues=team_revenues,
        status_users=status_users,

        status_by_user=status_by_user,
        all_statuses=all_statuses,
        
        pipelines=pipelines,

        upcoming_deadlines=upcoming_deadlines,
        overdue_pipelines=overdue_pipelines,
        history=history,
        history_users=history_users,
    )

from datetime import date


@app.route("/executive-dashboard")
def executive_dashboard():

    # =====================================================
    # SECURITY
    # =====================================================

    if "user_id" not in session:
        return redirect(url_for("login"))

    role = session.get("role")

    allowed_roles = app.config.get(
        "EXECUTIVE_DASHBOARD_ROLES",
        set()
    )

    if role not in allowed_roles:
        return redirect(url_for("login"))


    first_name = session.get("first_name", "")
    cursor = conn.cursor()


    # =====================================================
    # GET SALES ORGANIZATION
    #
    # We load the sales hierarchy globally rather than
    # tying the dashboard to a specific HOD.
    # =====================================================

    cursor.execute("""
        SELECT
            EmpID,
            EmployeeName,
            FirstName,
            LastName,
            Role,
            ManagerID
        FROM Users
        WHERE IsActive = 1
          AND Role IN (
              'Regional Head',
              'Regional Manager',
              'Team Lead',
              'EDO'
          )
    """)

    user_rows = cursor.fetchall()


    users = {}

    for row in user_rows:

        users[row[0]] = {
            "EmpID": row[0],
            "EmployeeName": row[1],
            "FirstName": row[2],
            "LastName": row[3],
            "Role": row[4],
            "ManagerID": row[5]
        }


    # =====================================================
    # USERS BY ROLE
    # =====================================================

    regional_heads = [
        u for u in users.values()
        if u["Role"] == "Regional Head"
    ]

    regional_managers = [
        u for u in users.values()
        if u["Role"] == "Regional Manager"
    ]

    team_leads = [
        u for u in users.values()
        if u["Role"] == "Team Lead"
    ]

    edos = [
        u for u in users.values()
        if u["Role"] == "EDO"
    ]


    # =====================================================
    # EMPLOYEE LOOKUP
    #
    # Pipelines.[Account Manager]
    # matches Users.EmployeeName
    # =====================================================

    employee_lookup = {}

    for user in users.values():

        if user["EmployeeName"]:

            employee_lookup[
                user["EmployeeName"]
                .strip()
                .lower()
            ] = user


    # =====================================================
    # FIND MANAGEMENT ANCESTOR
    # =====================================================

    def find_ancestor(user, required_role):

        current = user

        while current:

            if current["Role"] == required_role:
                return current

            manager_id = current["ManagerID"]

            if manager_id is None:
                return None

            current = users.get(manager_id)

        return None


    # =====================================================
    # GET PIPELINES
    #
    # IMPORTANT:
    # Uses canonical EmployeeName matching.
    # =====================================================

    cursor.execute("""
        SELECT
            p.PipelineID,                    -- 0
            p.[Account Manager],             -- 1
            p.[Vertical],                    -- 2
            p.[Account Name],                -- 3
            p.[Product],                     -- 4
            p.[Region],                      -- 5
            p.[MRC],                         -- 6
            p.[Contract Duration (Months)],  -- 7
            p.[ARR],                         -- 8
            p.[Project OTC],                 -- 9
            p.[Total Project Revenue],       -- 10
            p.[Estimated Closure Date],      -- 11
            p.[Estimated Closure Month],     -- 12
            p.EstimatedClosureDateFull,      -- 13
            p.[Sales Cycle Status],          -- 14
            p.[Next Action]                  -- 15

        FROM Pipelines p

        INNER JOIN Users u
            ON LTRIM(RTRIM(p.[Account Manager])) =
               LTRIM(RTRIM(u.EmployeeName))

        WHERE u.IsActive = 1
          AND u.Role IN (
              'Regional Head',
              'Regional Manager',
              'Team Lead',
              'EDO'
          )

        ORDER BY
            CASE
                WHEN p.EstimatedClosureDateFull IS NULL
                THEN 1
                ELSE 0
            END,
            p.EstimatedClosureDateFull ASC,
            p.[Account Name]
    """)

    pipeline_rows = cursor.fetchall()


    # =====================================================
    # STATUS GROUPS
    # =====================================================

    ACTIVE_STATUSES = {
        "Customer Visit (20%)",
        "Ask for Proposal (40%)",
        "Negotiations (60%)",
        "Documentation/Acceptance/Processing (80%)"
    }

    WON_STATUS = "System Entry/Revenue Locked (100%)"

    LOST_STATUSES = {
        "Lost to Competitor",
        "Retired - No Decision"
    }


    # =====================================================
    # ANALYTICS STRUCTURES
    # =====================================================

    pipelines = []

    total_revenue = 0
    total_mrc = 0
    total_otc = 0
    active_count = 0
    overdue_count = 0
    upcoming_count = 0

    revenue_by_rh = {}
    revenue_by_region = {}
    status_counts = {}
    status_metrics = {}

    product_pipeline_counts = {}
    product_revenue = {}
    product_active_counts = {}
    product_closed_counts = {}

    account_manager_revenue = {}

    products = set()
    regions = set()

    upcoming_deadlines = []
    overdue_pipelines = []

    account_managers_with_pipelines = set()

    today = date.today()


    # =====================================================
    # PROCESS PIPELINES
    # =====================================================

    for row in pipeline_rows:

        account_manager = row[1]

        owner = None

        if account_manager:

            owner = employee_lookup.get(
                account_manager.strip().lower()
            )


        # ---------------------------------------------
        # HIERARCHY
        # ---------------------------------------------

        regional_head = (
            find_ancestor(owner, "Regional Head")
            if owner else None
        )

        regional_manager = (
            find_ancestor(owner, "Regional Manager")
            if owner else None
        )

        team_lead = (
            find_ancestor(owner, "Team Lead")
            if owner else None
        )


        rh_name = (
            regional_head["EmployeeName"]
            if regional_head
            else ""
        )

        rm_name = (
            regional_manager["EmployeeName"]
            if regional_manager
            else ""
        )

        tl_name = (
            team_lead["EmployeeName"]
            if team_lead
            else ""
        )


        # ---------------------------------------------
        # CORRECT COLUMN MAPPING
        # ---------------------------------------------

        mrc = row[6] or 0
        arr = row[8] or 0
        project_otc = row[9] or 0
        revenue = row[10] or 0

        closure_date = row[13]

        status = row[14]
        product = row[4]
        region = row[5]


        # pyodbc normally returns DATE as datetime.date.
        # This also handles string values safely.
        if closure_date and isinstance(closure_date, str):

            try:
                closure_date = date.fromisoformat(
                    closure_date[:10]
                )
            except ValueError:
                closure_date = None


        # ---------------------------------------------
        # TOTALS
        # ---------------------------------------------

        total_revenue += revenue
        total_mrc += mrc
        total_otc += project_otc


        if account_manager:
            account_managers_with_pipelines.add(
                account_manager
            )


        # ---------------------------------------------
        # ACTIVE PIPELINES
        # ---------------------------------------------

        is_active = status in ACTIVE_STATUSES

        if is_active:
            active_count += 1


        # ---------------------------------------------
        # OVERDUE / UPCOMING
        # ---------------------------------------------

        days_remaining = None

        if closure_date:

            days_remaining = (
                closure_date - today
            ).days


            if is_active and closure_date < today:

                overdue_count += 1

                overdue_pipelines.append({
                    "PipelineID": row[0],
                    "AccountName": row[3],
                    "AccountManager": account_manager,
                    "Product": product,
                    "Status": status,
                    "ClosureDate": closure_date,
                    "DaysOverdue": abs(days_remaining)
                })


            elif (
                is_active
                and 0 <= days_remaining <= 7
            ):

                upcoming_count += 1

                upcoming_deadlines.append({
                    "PipelineID": row[0],
                    "AccountName": row[3],
                    "AccountManager": account_manager,
                    "Product": product,
                    "Status": status,
                    "ClosureDate": closure_date,
                    "DaysRemaining": days_remaining
                })


        # ---------------------------------------------
        # REVENUE BY REGIONAL HEAD
        # ---------------------------------------------

        display_rh = (
            rh_name
            if rh_name
            else "Unassigned"
        )

        revenue_by_rh[display_rh] = (
            revenue_by_rh.get(display_rh, 0)
            + revenue
        )


        # ---------------------------------------------
        # REVENUE BY REGION
        # ---------------------------------------------

        if region:

            regions.add(region)

            revenue_by_region[region] = (
                revenue_by_region.get(region, 0)
                + revenue
            )


        # ---------------------------------------------
        # STATUS
        # ---------------------------------------------

        if status:

            status_counts[status] = (
                status_counts.get(status, 0)
                + 1
            )

            if status not in status_metrics:
                status_metrics[status] = {
                    "count": 0,
                    "revenue": 0,
                    "mrc": 0,
                    "otc": 0
                }

            status_metrics[status]["count"] += 1
            status_metrics[status]["revenue"] += revenue
            status_metrics[status]["mrc"] += mrc
            status_metrics[status]["otc"] += project_otc


        # ---------------------------------------------
        # PRODUCT ANALYTICS
        # ---------------------------------------------

        if product:

            products.add(product)

            product_pipeline_counts[product] = (
                product_pipeline_counts.get(
                    product,
                    0
                )
                + 1
            )

            product_revenue[product] = (
                product_revenue.get(
                    product,
                    0
                )
                + revenue
            )


            if status in ACTIVE_STATUSES:

                product_active_counts[product] = (
                    product_active_counts.get(
                        product,
                        0
                    )
                    + 1
                )

            else:

                product_closed_counts[product] = (
                    product_closed_counts.get(
                        product,
                        0
                    )
                    + 1
                )


        # ---------------------------------------------
        # ACCOUNT MANAGER REVENUE
        # ---------------------------------------------

        if account_manager:

            account_manager_revenue[
                account_manager
            ] = (
                account_manager_revenue.get(
                    account_manager,
                    0
                )
                + revenue
            )


        # ---------------------------------------------
        # PIPELINE RECORD
        # ---------------------------------------------

        pipelines.append({

            "PipelineID": row[0],

            "AccountManager": account_manager,

            "RegionalHead": rh_name,

            "RegionalManager": rm_name,

            "TeamLead": tl_name,

            "Vertical": row[2],

            "AccountName": row[3],

            "Product": product,

            "Region": region,

            "MRC": mrc,

            "ContractDuration": row[7],

            "ARR": arr,

            "ProjectOTC": project_otc,

            "TotalRevenue": revenue,

            "ClosureDateFull": closure_date,

            "Status": status,

            "NextAction": row[15],

            "DaysRemaining": days_remaining
        })


    # =====================================================
    # AVERAGES
    # =====================================================

    total_pipeline_count = len(pipelines)

    average_pipeline_value = (
        total_revenue / total_pipeline_count
        if total_pipeline_count
        else 0
    )


    # =====================================================
    # PRODUCT PERFORMANCE
    # =====================================================

    product_performance = []

    for product in sorted(products):

        pipeline_count = (
            product_pipeline_counts.get(
                product,
                0
            )
        )

        revenue = (
            product_revenue.get(
                product,
                0
            )
        )

        active = (
            product_active_counts.get(
                product,
                0
            )
        )

        closed = (
            product_closed_counts.get(
                product,
                0
            )
        )

        average_value = (
            revenue / pipeline_count
            if pipeline_count
            else 0
        )


        product_performance.append({

            "Product": product,

            "PipelineCount": pipeline_count,

            "ActiveCount": active,

            "ClosedCount": closed,

            "Revenue": revenue,

            "AverageValue": average_value
        })


    # Highest pipeline count first
    product_performance.sort(
        key=lambda x: x["PipelineCount"],
        reverse=True
    )


    # =====================================================
    # TOP ACCOUNT MANAGERS
    # =====================================================

    top_account_managers = [

        {
            "Name": name,
            "Revenue": revenue
        }

        for name, revenue
        in account_manager_revenue.items()
    ]

    top_account_managers.sort(
        key=lambda x: x["Revenue"],
        reverse=True
    )

    top_account_managers = (
        top_account_managers[:10]
    )


    # =====================================================
    # SORT DEADLINES
    # =====================================================

    upcoming_deadlines.sort(
        key=lambda x: x["ClosureDate"]
    )

    overdue_pipelines.sort(
        key=lambda x: x["DaysOverdue"],
        reverse=True
    )



    # =====================================================
    # SUMMARY
    # =====================================================

    summary = {

        "TotalRevenue": total_revenue,

        "ActivePipelines": active_count,

        "TotalMRC": total_mrc,

        "TotalOTC": total_otc,

        "AveragePipelineValue":
            average_pipeline_value,

        "OverduePipelines":
            overdue_count,

        "UpcomingDeadlines":
            upcoming_count,

        "AccountManagers":
            len(
                account_managers_with_pipelines
            ),

        "TotalPipelines":
            total_pipeline_count
    }


    cursor.close()


    # ========================================================
    # EDIT HISTORY - ADMIN ONLY
    # ========================================================

    history = []
    history_users = []

    if role == "Admin":

        history_cursor = conn.cursor()

        history_cursor.execute("""
            SELECT
                HistoryID,
                [Account Name],
                FieldName,
                OldValue,
                NewValue,
                EditedBy,
                EditedOn
            FROM dbo.History
            ORDER BY EditedOn DESC
        """)

        history = [
            {
                "HistoryID": row[0],
                "AccountName": row[1],
                "FieldName": row[2],
                "OldValue": row[3],
                "NewValue": row[4],
                "EditedBy": row[5],
                "EditedOn": row[6]
            }
            for row in history_cursor.fetchall()
        ]


        history_cursor.execute("""
            SELECT DISTINCT
                EditedBy
            FROM dbo.History
            WHERE EditedBy IS NOT NULL
            ORDER BY EditedBy
        """)

        history_users = [
            row[0]
            for row in history_cursor.fetchall()
        ]

        history_cursor.close()
    # =====================================================
    # RENDER
    # =====================================================

    return render_template(

        "executive_dashboard.html",

        first_name=first_name,

        viewer_role=role,

        summary=summary,

        regional_heads=regional_heads,

        regional_managers=regional_managers,

        team_leads=team_leads,

        edos=edos,

        products=sorted(products),

        regions=sorted(regions),

        pipelines=pipelines,

        revenue_by_rh=revenue_by_rh,

        revenue_by_region=revenue_by_region,

        status_counts=status_counts,
        status_metrics=status_metrics,

        product_performance=
            product_performance,

        product_pipeline_counts=
            product_pipeline_counts,

        product_revenue=
            product_revenue,

        product_active_counts=
            product_active_counts,

        product_closed_counts=
            product_closed_counts,

        top_account_managers=
            top_account_managers,

        upcoming_deadlines=
            upcoming_deadlines,

        overdue_pipelines=
            overdue_pipelines,

        history=
            history,

        history_users=
            history_users
    )


# ============================================================
# EXECUTIVE -> REGIONAL HEAD DRILL-DOWN
# ============================================================

@app.route("/executive-dashboard/regional-head/<int:regional_head_id>")
def executive_regional_head_dashboard(regional_head_id):

    # -------------------------
    # ACCESS CHECK
    # -------------------------

    if "user_id" not in session:
        return redirect(url_for("login"))

    role = (session.get("role") or "").strip()

    executive_roles = app.config.get(
        "EXECUTIVE_DASHBOARD_ROLES",
        set()
    )

    if role not in executive_roles:
        return redirect(url_for("login"))


    viewer_first_name = session.get(
        "first_name",
        ""
    )

    cursor = conn.cursor()


    # ========================================================
    # REGIONAL HEAD
    # ========================================================

    cursor.execute("""
        SELECT
            EmpID,
            EmployeeName,
            FirstName,
            LastName
        FROM Users
        WHERE
            EmpID = ?
            AND Role = 'Regional Head'
            AND IsActive = 1
    """, (regional_head_id,))

    regional_head_row = cursor.fetchone()

    if not regional_head_row:
        cursor.close()
        return redirect(
            url_for("executive_dashboard")
        )

    regional_head_name = regional_head_row[1]


    # ========================================================
    # USERS IN THIS REGIONAL HEAD ORGANIZATION
    # ========================================================

    cursor.execute("""
        WITH UserHierarchy AS (

            SELECT
                EmpID,
                EmployeeName,
                Role,
                ManagerID

            FROM Users

            WHERE
                EmpID = ?
                AND IsActive = 1


            UNION ALL


            SELECT
                u.EmpID,
                u.EmployeeName,
                u.Role,
                u.ManagerID

            FROM Users u

            INNER JOIN UserHierarchy h
                ON u.ManagerID = h.EmpID

            WHERE
                u.IsActive = 1
        )

        SELECT
            EmpID,
            EmployeeName,
            Role,
            ManagerID

        FROM UserHierarchy

        ORDER BY
            CASE Role
                WHEN 'Regional Head' THEN 1
                WHEN 'Regional Manager' THEN 2
                WHEN 'Team Lead' THEN 3
                WHEN 'EDO' THEN 4
                ELSE 5
            END,
            EmployeeName

        OPTION (MAXRECURSION 100)
    """, (regional_head_id,))


    regional_users = [
        {
            "EmpID": row[0],
            "FullName": row[1],
            "Role": row[2],
            "ManagerID": row[3]
        }
        for row in cursor.fetchall()
    ]


    regional_managers = [
        user
        for user in regional_users
        if user["Role"] == "Regional Manager"
    ]


    # ========================================================
    # SUMMARY
    # ========================================================

    cursor.execute("""
        WITH UserHierarchy AS (

            SELECT
                EmpID,
                EmployeeName,
                Role,
                ManagerID

            FROM Users

            WHERE
                EmpID = ?
                AND IsActive = 1


            UNION ALL


            SELECT
                u.EmpID,
                u.EmployeeName,
                u.Role,
                u.ManagerID

            FROM Users u

            INNER JOIN UserHierarchy h
                ON u.ManagerID = h.EmpID

            WHERE
                u.IsActive = 1
        )

        SELECT
            COALESCE(
                SUM(p.[MRC]),
                0
            ),

            COALESCE(
                SUM(p.[Project OTC]),
                0
            ),

            COALESCE(
                SUM(p.[Total Project Revenue]),
                0
            ),

            COALESCE(
                SUM(
                    CASE
                        WHEN p.[Sales Cycle Status] IN (
                            'Customer Visit (20%)',
                            'Ask for Proposal (40%)',
                            'Negotiations (60%)',
                            'Documentation/Acceptance/Processing (80%)'
                        )
                        THEN 1
                        ELSE 0
                    END
                ),
                0
            )

        FROM UserHierarchy uh

        LEFT JOIN Pipelines p
            ON LTRIM(RTRIM(p.[Account Manager])) =
               LTRIM(RTRIM(uh.EmployeeName))

        OPTION (MAXRECURSION 100)
    """, (regional_head_id,))


    summary_row = cursor.fetchone()

    summary = {
        "TotalMRC": summary_row[0] or 0,
        "TotalOTC": summary_row[1] or 0,
        "TotalRevenue": summary_row[2] or 0,
        "ActivePipelines": summary_row[3] or 0
    }


    # ========================================================
    # REVENUE BY REGIONAL MANAGER
    # ========================================================

    cursor.execute("""
        WITH RMHierarchy AS (

            SELECT
                rm.EmpID,
                rm.EmployeeName,
                rm.ManagerID,

                rm.EmpID AS RegionalManagerID,
                rm.EmployeeName AS RegionalManagerName

            FROM Users rm

            WHERE
                rm.ManagerID = ?
                AND rm.Role = 'Regional Manager'
                AND rm.IsActive = 1


            UNION ALL


            SELECT
                u.EmpID,
                u.EmployeeName,
                u.ManagerID,

                h.RegionalManagerID,
                h.RegionalManagerName

            FROM Users u

            INNER JOIN RMHierarchy h
                ON u.ManagerID = h.EmpID

            WHERE
                u.IsActive = 1
        )

        SELECT
            h.RegionalManagerID,
            h.RegionalManagerName,

            COALESCE(
                SUM(p.[Total Project Revenue]),
                0
            ) AS Revenue

        FROM RMHierarchy h

        LEFT JOIN Pipelines p
            ON LTRIM(RTRIM(p.[Account Manager])) =
               LTRIM(RTRIM(h.EmployeeName))

        GROUP BY
            h.RegionalManagerID,
            h.RegionalManagerName

        ORDER BY
            h.RegionalManagerName

        OPTION (MAXRECURSION 100)
    """, (regional_head_id,))


    manager_names = []
    manager_revenues = []

    for row in cursor.fetchall():
        manager_names.append(row[1])
        manager_revenues.append(row[2] or 0)


    # ========================================================
    # PIPELINE STATUS BY PERSON
    # ========================================================

    cursor.execute("""
        WITH UserHierarchy AS (

            SELECT
                EmpID,
                EmployeeName,
                Role,
                ManagerID

            FROM Users

            WHERE
                EmpID = ?
                AND IsActive = 1


            UNION ALL


            SELECT
                u.EmpID,
                u.EmployeeName,
                u.Role,
                u.ManagerID

            FROM Users u

            INNER JOIN UserHierarchy h
                ON u.ManagerID = h.EmpID

            WHERE
                u.IsActive = 1
        )

        SELECT
            uh.EmpID,
            uh.EmployeeName,
            p.[Sales Cycle Status],

            COUNT(p.PipelineID) AS StatusCount,

            COALESCE(
                SUM(p.[Total Project Revenue]),
                0
            ) AS TotalRevenue,

            COALESCE(
                SUM(p.[MRC]),
                0
            ) AS TotalMRC,

            COALESCE(
                SUM(p.[Project OTC]),
                0
            ) AS TotalOTC

        FROM UserHierarchy uh

        LEFT JOIN Pipelines p
            ON LTRIM(RTRIM(p.[Account Manager])) =
               LTRIM(RTRIM(uh.EmployeeName))

        GROUP BY
            uh.EmpID,
            uh.EmployeeName,
            p.[Sales Cycle Status]

        ORDER BY
            uh.EmployeeName,
            p.[Sales Cycle Status]

        OPTION (MAXRECURSION 100)
    """, (regional_head_id,))


    status_by_user = {}

    for row in cursor.fetchall():

        emp_id = str(row[0])
        employee_name = row[1]
        status = row[2]

        count = row[3] or 0
        revenue = row[4] or 0
        mrc = row[5] or 0
        otc = row[6] or 0

        if emp_id not in status_by_user:
            status_by_user[emp_id] = {
                "name": employee_name,
                "statuses": {}
            }

        if status:
            status_by_user[emp_id]["statuses"][status] = {
                "count": count,
                "revenue": revenue,
                "mrc": mrc,
                "otc": otc
            }


    all_statuses = {}

    for user_data in status_by_user.values():

        for status, metrics in user_data["statuses"].items():

            if status not in all_statuses:
                all_statuses[status] = {
                    "count": 0,
                    "revenue": 0,
                    "mrc": 0,
                    "otc": 0
                }

            all_statuses[status]["count"] += metrics["count"]
            all_statuses[status]["revenue"] += metrics["revenue"]
            all_statuses[status]["mrc"] += metrics["mrc"]
            all_statuses[status]["otc"] += metrics["otc"]


    # ========================================================
    # PIPELINES + HIERARCHY LABELS
    # ========================================================

    cursor.execute("""
        WITH UserHierarchy AS (

            SELECT
                EmpID,
                EmployeeName,
                Role,
                ManagerID,

                CAST(NULL AS VARCHAR(255))
                    AS RegionalManagerName,

                CAST(NULL AS VARCHAR(255))
                    AS TeamLeadName

            FROM Users

            WHERE
                EmpID = ?
                AND IsActive = 1


            UNION ALL


            SELECT
                u.EmpID,
                u.EmployeeName,
                u.Role,
                u.ManagerID,

                CASE
                    WHEN u.Role = 'Regional Manager'
                        THEN u.EmployeeName
                    ELSE h.RegionalManagerName
                END AS RegionalManagerName,

                CASE
                    WHEN u.Role = 'Team Lead'
                        THEN u.EmployeeName
                    ELSE h.TeamLeadName
                END AS TeamLeadName

            FROM Users u

            INNER JOIN UserHierarchy h
                ON u.ManagerID = h.EmpID

            WHERE
                u.IsActive = 1
        )

        SELECT
            uh.EmpID,
            p.[Account Manager],
            uh.RegionalManagerName,
            uh.TeamLeadName,

            p.[Vertical],
            p.[Account Name],
            p.[Product],
            p.[Region],
            p.[MRC],
            p.[Contract Duration (Months)],
            p.[ARR],
            p.[Project OTC],
            p.[Total Project Revenue],
            p.EstimatedClosureDateFull,
            p.[Sales Cycle Status],
            p.[Next Action]

        FROM Pipelines p

        INNER JOIN UserHierarchy uh
            ON LTRIM(RTRIM(p.[Account Manager])) =
               LTRIM(RTRIM(uh.EmployeeName))

        ORDER BY
            p.[Account Manager],
            p.[Account Name]

        OPTION (MAXRECURSION 100)
    """, (regional_head_id,))


    pipelines = [
        {
            "EmpID": row[0],
            "AccountManager": row[1],
            "RegionalManager": row[2],
            "TeamLead": row[3],
            "Vertical": row[4],
            "AccountName": row[5],
            "Product": row[6],
            "Region": row[7],
            "MRC": row[8],
            "ContractDuration": row[9],
            "ARR": row[10],
            "ProjectOTC": row[11],
            "TotalProjectRevenue": row[12],
            "EstimatedClosureDateFull": row[13],
            "SalesCycleStatus": row[14],
            "NextAction": row[15]
        }
        for row in cursor.fetchall()
    ]


    cursor.close()


    return render_template(
        "executive_regional_head.html",

        viewer_first_name=viewer_first_name,
        viewer_role=role,

        regional_head_name=regional_head_name,

        regional_users=regional_users,
        regional_managers=regional_managers,

        summary=summary,

        manager_names=manager_names,
        manager_revenues=manager_revenues,

        status_by_user=status_by_user,
        all_statuses=all_statuses,

        pipelines=pipelines
    )



if __name__ == "__main__":
    app.run(debug=True)
