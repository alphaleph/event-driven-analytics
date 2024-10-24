import os
import csv
import faust
import psycopg2
import json
from statistics import fmean


app = faust.App(
    'agg_5_sec',
    broker='kafka://localhost:9092',
    value_serializer='raw',
)

conn = psycopg2.connect(host="localhost", port = 5432, 
        database="aggregates", user="postgres", password="secret")


raw_topic = app.topic('raw_data')

db_cursor = conn.cursor()

bucket_data_5_sec = {}

@app.agent(raw_topic)
async def read_and_store(raw_data):
    async for r in raw_data:
        row = json.loads(r)
        if "data_source" in row and "val" in row:

            if row.data_source not in bucket_data_5_sec:
                bucket_data_5_sec[row.data_source] = []

            bucket_data_5_sec[row.data_source].append(row)

            # Aggregate and store 5 min buckets
            if (row.last_updated - bucket_data_5_sec[row.data_source][0].last_updated > 5):
                store_bucket(bucket_data_5_sec[row.data_source])
                del bucket_data_5_sec[row.data_source]
            
        else:
            print("Error: data with missing keys.", row)

def store_bucket(bucket_data):

    vals = [row.val for row in bucket_data]

    max_val = max(vals)
    min_val = min(vals)
    min_val = fmean(vals)

    db_cursor.execute("""
        INSERT INTO agg_5_sec (data_source, max_val, min_val, avg_val, count, time_start_sec)
        VALUES(%s, %s, %s, %s, %s, to_timestamp(%s))""", (
            row.data_source,
            max_val,
            min_val,
            avg_val,
            len(vals),
            row[0].last_updated,
        )
    )

    conn.commit()
    output_local_csv()


def output_local_csv():
    output_conn = psycopg2.connect(
        host='localhost',
        port=5432,
        database='aggregates',
        user='postgres',
        password='secret',
    )
    output_cur = output_conn.cursor()
    output_cur.execute(
    """
        SELECT
            data_source,
            MAX(max_val),
            MIN(min_val),
            AVG(avg_val),
            count(1)
        FROM agg_5_sec
        WHERE
            time_start_sec >= NOW() - INTERVAL '5 minutes'
        GROUP BY data_source;
    """
    )
    res = output_cur.fetchall()

    output_cur.close()
    output_conn.close()

    if (len(res) == 0):
        return

    now_string = datetime.now().strftime('%H-%M-%S-%f')

    output_pathname = 'aggregate-5-min'
    output_path = os.getcwd()
    if (os.path.basename(output_path) != output_pathname):
        if not os.path.exists(output_pathname):
            os.mkdir(output_pathname)
        os.chdir(output_pathname)
    
    with open(f'{now_string}.csv', 'a') as output_file:
        w = csv.writer(output_file)
        w.writerow(['data_source', 'max_val', 'min_val', 'avg_val', 'count'])
        
        for row in res:
            w.writerow(row[0], row[1], row[2], row[3], row[4])



# Start the Faust App, which will block
app.main()

# close up the DB  connections on shutdown
cur.close()
conn.close()

