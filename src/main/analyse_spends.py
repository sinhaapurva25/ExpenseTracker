from pyspark.sql import SparkSession
from pyspark.sql.functions import sum as _sum

spark = SparkSession.builder \
    .appName("Zoho Sheet Expenditure Analysis") \
    .master("local[*]") \
    .getOrCreate()

csvPath = r"C:\\myWork\\ExpenseTracker\\src\\resources\\monthly_data\\Expenditures_20250701-20260630.csv"
df = spark.read.option("header", "true").option("inferSchema", "true").csv(csvPath)

df.show()

resultDF = df.groupBy("Category").agg(_sum("Expenditure").alias("Total_Expenditure"))
resultDF.show()
spark.stop()