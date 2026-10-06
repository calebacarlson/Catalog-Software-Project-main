import csv
from crud import *

def import_csv_mongodb(file_name_, start_col_, end_col_):
# takes file name and the columns that you want to import

    start_col_ -= 1

    with open(file_name_, "r") as f:

        reader = csv.reader(f)

        headers = next(reader)

        for row in reader:

            mongodb_row = {}

            for col in range(start_col_, end_col_):

                mongodb_row[headers[col]] = row[col]

            create_course(mongodb_row)



