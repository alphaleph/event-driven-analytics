# To run: `poetry run python3 producer.py worker`

import faust
import random
import time
from datetime import datetime

# Mock data generation
data_source_vals = {}
INIT_VAL = 50
FLUX_COEFFICIENT = 5
DATA_SOURCES = ['a', 'b', 'c']

def update_val_for_data_source(data_source_key):
    if data_source_vals.get(data_source_key) == None:
        new_val = INIT_VAL
    else:
        new_val = data_source_vals[data_source_key] + (random.random()-0.5)*FLUX_COEFFICIENT

    data_source_vals[data_source_key] = new_val

    return data_source_vals[data_source_key]


# Faust Records
class Raw(faust.Record):
    data_source: str
    val: str
    last_updated: str

# Faust App
app = faust.App('mock_data', broker='kafka://localhost:9092')
raw_topic = app.topic('raw_data', value_type=Raw)

@app.timer(interval=1.0)
async def send_messages(m):

    for d in DATA_SOURCES:
        new_val = update_val_for_data_source(d)
        timestamp = datetime.now()

        await raw_topic.send(
            value=Raw(
                data_source=d,
                val=new_val,
                last_updated=timestamp
            ),
        )


if __name__ == '__main__':
    app.main()