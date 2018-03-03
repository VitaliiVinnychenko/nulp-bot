from constants import db_conn


if __name__ == '__main__':
    with db_conn.cursor() as cur, open('script.sql', 'r') as sql_file:
        cur.execute(sql_file.read())

    db_conn.commit()
