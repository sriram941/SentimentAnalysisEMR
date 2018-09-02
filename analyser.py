from pyspark.sql import SparkSession
from pyspark.sql.functions import col
from pyspark.sql.types import StructType, StructField, StringType
import timeit
import re


data_file = ''


def raw_df():
    df = spark.read.option('header', 'true').option('encoding', 'utf-8').csv(data_file)
    # df = spark.read.option('header', 'true').option('encoding', 'utf-8').csv('s3n://cs643project/dataset1.csv')
    return df


def raw_df_sampling():
    df = raw_df()
    for i in range(1, 10):
        df.sample(False, 0.1*i, 42).toPandas().to_csv('./data/dataset' + str(i) + '.csv', encoding='utf-8')


def word_parser():
    df = raw_df().select(['SentimentText', 'Sentiment'])
    rdd = df.rdd.flatMap(lambda x: [[ele.lower(), x[1]] for ele in x[0].split()])\
            .filter(lambda x: len(re.compile("[^a-zA-Z]+").findall(x[0])) == 0)
    # print rdd.take(5)
    df = spark.createDataFrame(rdd, ['word', 'Sentiment'])
    return df


def stop_word():
    schema = StructType([StructField("stopword", StringType(), True)])
    df = spark.read.option('header', 'false').csv('./data/stopwords_en.txt', schema=schema)
    # df.show()
    return df.rdd.map(lambda x: list(x)[0]).collect()


def word_count(label):
    df = word_parser()\
        .where(col('Sentiment').isin(label))
    # df = df.where(col('word').isin(stop_word())==False)
    df = df.select(['word']).groupBy(['word']).count().sort(col("count").desc())
    df.show()
    return df


def common_onkey(df1, df2):
    df1 = df1.withColumnRenamed("count", "count1")
    df2 = df2.withColumnRenamed("count", "count2")
    df = df1.join(df2, ['word'], 'inner').sort(col("count1").desc())
    print 'common onkey: '
    df.show()
    return df, df.select(['word']).rdd.map(list).flatMap(lambda x: x).collect()


def exclude_onkey(df1, df2):
    _, common_keys = common_onkey(df1, df2)
    # print common_keys
    df1 = df1.where(col('word').isin(common_keys)==False)
    df2 = df2.where(col('word').isin(common_keys)==False)
    print 'exclude onkey: '
    df1.show()
    df2.show()
    return df1, df2


def tweet_length(label):
    rdd = raw_df()\
        .where(col('Sentiment').isin(label))\
        .select(['SentimentText']).rdd.map(lambda x: [len(str(x)) if x else 0])
    df = spark.createDataFrame(rdd, ['length'])
    print "tweet length: "
    df.show()
    df.describe().show()
    return df


def prob_in_tweet(w):
    count_0 = word_count(['0']).where(col("word") == w).select(col("count")).rdd.collect()[0][0]
    count_1 = word_count(['1']).where(col("word") == w).select(col("count")).rdd.collect()[0][0]
    total = count_0 + count_1
    print w, "-> probability on 0 and on 1: "
    print count_0*1.0/total, count_1*1.0/total

# What are the most popular words in positive or negative tweets?
# Which tweets are longer? Positive or Negative?
# What are the chances a positive/negative tweet will contain certain words?

def master():
    time_cost = []
    file_name_prefix= "s3n://cs643project/dataset" 
    file_name_postfix = ".csv"

    for i in range(1, 5):
        i = 4
        global data_file
        data_file = file_name_prefix + str(i) + file_name_postfix
        start = timeit.default_timer()
        df1 = word_count(['0'])
        df2 = word_count(['1'])
        exclude_onkey(df1, df2)
        tweet_length(['0'])
        prob_in_tweet('like')
        stop = timeit.default_timer()
        time_cost.append(stop - start)
        break

    print "time cost for all input files : ", time_cost 

if __name__ == "__main__":
    spark = SparkSession \
        .builder \
        .appName("twitter data") \
        .getOrCreate()

    spark.sparkContext.setLogLevel("ERROR")

    master()
