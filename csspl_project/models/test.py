
import xmlrpc.client
# import pyodbc
import psycopg2
import psycopg2.extras

url = "http://localhost:8069/"
db = "css_05_jun"
username = "info@closyss.com"
password = "1"

common = xmlrpc.client.ServerProxy('{}/xmlrpc/2/common'.format(url))
common.version()

uid = common.authenticate(db, username, password, {})

models = xmlrpc.client.ServerProxy('{}/xmlrpc/2/object'.format(url))

# Define the connection string
conn_str = psycopg2.connect(database="css_9_jul", user='odoo16e', host='localhost', password="1", port=5432)

# Create a cursor
cursor = conn_str.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

# Execute a query
cursor.execute("SELECT account_id, move_line_id, amount FROM account_analytic_line")

# Fetch the results
rows = cursor.fetchall()
dict_result = [dict(row) for row in rows]

# for rec in dict_result:
query = """insert into account_analytic_line account_id, move_line_id, amount values {}""".format((rec.get('account_id'), rec.get('move_line_id'), float(rec.get('amount'))for rec in dict_result))
models.execute_kw(db, uid, password, 'account.analytic.line', 'sql_query', 'search', query)
# print(data)
# Close the connection
conn_str.close()