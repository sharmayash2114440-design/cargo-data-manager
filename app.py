import csv
from io import StringIO
import sqlite3
import sys
import webbrowser
from threading import Timer
from pathlib import Path

from flask import Flask, render_template, request, redirect, session, url_for, Response
from werkzeug.security import check_password_hash, generate_password_hash

if getattr(sys, "frozen", False):
    APP_DIR = Path(sys.executable).parent
    RESOURCE_DIR = Path(sys._MEIPASS)
else:
    APP_DIR = Path(__file__).parent
    RESOURCE_DIR = APP_DIR

app = Flask(
    __name__,
    template_folder=str(RESOURCE_DIR / "templates"),
    static_folder=str(RESOURCE_DIR / "static")
)
app.config["SECRET_KEY"] = "cargo-manager-secret-key"

DATABASE = APP_DIR / "cargo_data.db"

RECORD_FIELDS = (
    "wt_slip_date", "handover_status", "bill_no", "lot_no",
    "loading_port", "balance_bags", "vehicle_no", "received_bags",
    "carting_date", "shipper", "invoice_no", "shipping_bill_no",
    "shipping_bill_date", "hs_code", "bags", "weight",
    "container_count", "container_size", "visual", "description",
    "destination", "consignee", "booking_no", "booking_party",
    "vessel", "etd", "cutoff", "shipping_line", "container_no",
    "gate", "pickup_date", "gatein", "egm_no_date",
    "scroll_no_date", "current_queue"
)


def get_connection():
    connection = sqlite3.connect(DATABASE)
    connection.row_factory = sqlite3.Row
    return connection


def create_database():
    with get_connection() as connection:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                role TEXT NOT NULL
            )
        """)

        connection.execute("""
            CREATE TABLE IF NOT EXISTS cargo_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                wt_slip_date TEXT,
                handover_status TEXT,
                bill_no TEXT,
                lot_no TEXT,
                loading_port TEXT,
                balance_bags TEXT,
                vehicle_no TEXT,
                received_bags TEXT,
                carting_date TEXT,
                shipper TEXT,
                invoice_no TEXT,
                shipping_bill_no TEXT,
                shipping_bill_date TEXT,
                hs_code TEXT,
                bags TEXT,
                weight TEXT,
                container_count TEXT,
                container_size TEXT,
                visual TEXT,
                description TEXT,
                destination TEXT,
                consignee TEXT,
                booking_no TEXT,
                booking_party TEXT,
                vessel TEXT,
                etd TEXT,
                cutoff TEXT,
                shipping_line TEXT,
                container_no TEXT,
                gate TEXT,
                pickup_date TEXT,
                gatein TEXT,
                egm_no_date TEXT,
                scroll_no_date TEXT,
                current_queue TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        admin = connection.execute(
            "SELECT id FROM users WHERE username = ?",
            ("admin",)
        ).fetchone()

        if admin is None:
            connection.execute(
                "INSERT INTO users (username, password, role) VALUES (?, ?, ?)",
                ("admin", generate_password_hash("admin123"), "admin")
            )


create_database()


@app.route("/", methods=["GET", "POST"])
def login():
    error = None

    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"]

        with get_connection() as connection:
            user = connection.execute(
                "SELECT * FROM users WHERE username = ?",
                (username,)
            ).fetchone()

        if user and check_password_hash(user["password"], password):
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            return redirect(url_for("dashboard"))

        error = "Username or password is incorrect."

    return render_template("index.html", error=error)


@app.route("/dashboard", methods=["GET", "POST"])
def dashboard():
    if "user_id" not in session:
        return redirect(url_for("login"))

    if request.method == "POST":
        values = [request.form.get(field, "").strip() for field in RECORD_FIELDS]
        columns = ", ".join(RECORD_FIELDS)
        placeholders = ", ".join(["?"] * len(RECORD_FIELDS))

        with get_connection() as connection:
            connection.execute(
                f"INSERT INTO cargo_records ({columns}) VALUES ({placeholders})",
                values
            )

        return redirect(url_for("dashboard", saved="1"))

    return render_template(
        "dashboard.html",
        username=session["username"],
        saved=request.args.get("saved")
    )

@app.route("/records")
def records():
    if "user_id" not in session:
        return redirect(url_for("login"))

    query = request.args.get("query", "").strip()

    with get_connection() as connection:
        if query:
            search_value = f"%{query}%"
            records = connection.execute("""
                SELECT * FROM cargo_records
                WHERE booking_no LIKE ?
                   OR bill_no LIKE ?
                   OR invoice_no LIKE ?
                   OR container_no LIKE ?
                   OR shipper LIKE ?
                ORDER BY id DESC
            """, (
                search_value,
                search_value,
                search_value,
                search_value,
                search_value
            )).fetchall()
        else:
            records = connection.execute("""
                SELECT * FROM cargo_records
                ORDER BY id DESC
            """).fetchall()

    return render_template("records.html", records=records, query=query)

@app.post("/records/<int:record_id>/delete")
def delete_record(record_id):
    if "user_id" not in session:
        return redirect(url_for("login"))

    with get_connection() as connection:
        connection.execute(
            "DELETE FROM cargo_records WHERE id = ?",
            (record_id,)
        )

    return redirect(url_for("records"))

@app.route("/records/<int:record_id>/edit", methods=["GET", "POST"])
def edit_record(record_id):
    if "user_id" not in session:
        return redirect(url_for("login"))

    with get_connection() as connection:
        if request.method == "POST":
            values = [
                request.form.get(field, "").strip()
                for field in RECORD_FIELDS
            ]

            updates = ", ".join(
                [f"{field} = ?" for field in RECORD_FIELDS]
            )

            connection.execute(
                f"UPDATE cargo_records SET {updates} WHERE id = ?",
                values + [record_id]
            )

            return redirect(url_for("records"))

        record = connection.execute(
            "SELECT * FROM cargo_records WHERE id = ?",
            (record_id,)
        ).fetchone()

    if record is None:
        return redirect(url_for("records"))

    return render_template("edit.html", record=record)

@app.get("/records/export")
def export_records():
    if "user_id" not in session:
        return redirect(url_for("login"))

    with get_connection() as connection:
        records = connection.execute(
            "SELECT * FROM cargo_records ORDER BY id DESC"
        ).fetchall()

    output = StringIO()
    writer = csv.writer(output)

    writer.writerow([
        "ID",
        "WT Slip Date",
        "Handover Status",
        "Bill No.",
        "Lot No.",
        "Loading Port",
        "Shipper",
        "Invoice No.",
        "Booking No.",
        "Container No.",
        "Destination",
        "Created At"
    ])

    for record in records:
        writer.writerow([
            record["id"],
            record["wt_slip_date"],
            record["handover_status"],
            record["bill_no"],
            record["lot_no"],
            record["loading_port"],
            record["shipper"],
            record["invoice_no"],
            record["booking_no"],
            record["container_no"],
            record["destination"],
            record["created_at"]
        ])

    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={
            "Content-Disposition": "attachment; filename=cargo_records.csv"
        }
    )

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


if __name__ == "__main__":
    Timer(
        1,
        lambda: webbrowser.open("http://127.0.0.1:5000")
    ).start()

    app.run(debug=False)