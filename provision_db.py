import mysql.connector
from mysql.connector import Error

def execute_sql_script(sql_file_path, host='localhost', user='root', password=''):
    """
    Executes all SQL statements in the given .sql file.
    """
    try:
        # Connect to MySQL server
        connection = mysql.connector.connect(
            host=host,
            user=user,
            password=password,
            autocommit=True
        )

        if connection.is_connected():
            print(f"Connected to MySQL server at {host} as {user}")

            cursor = connection.cursor()

            # Read SQL file content
            with open(sql_file_path, 'r') as file:
                sql_script = file.read()

            # Split and execute commands one by one
            commands = [cmd.strip() for cmd in sql_script.split(';') if cmd.strip()]
            for command in commands:
                try:
                    cursor.execute(command)
                except Error as e:
                    print(f"Skipping failed command:\n{command}\nError: {e}")

            print("🎉 Database schema successfully provisioned!")

    except Error as e:
        print(f"Error connecting to MySQL: {e}")

    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()
            print("MySQL connection closed.")


if __name__ == "__main__":
    # Change these if needed
    SQL_FILE = "database_schema.sql"
    HOST = "localhost"
    USER = "root"
    PASSWORD = "root"  # Set your MySQL password if required

    execute_sql_script(SQL_FILE, host=HOST, user=USER, password=PASSWORD)
