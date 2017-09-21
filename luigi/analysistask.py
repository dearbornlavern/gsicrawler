import datetime
import json
import random
import imp
import re
import requests
import os
import time
from rdflib import Graph, plugin
from rdflib.serializer import Serializer

import luigi
import tweepy
from luigi.contrib.esindex import CopyToIndex
from scrapy.crawler import CrawlerProcess
from scrapers.foursquare import FourSquareSpider
import subprocess
import scraperReddit
from scrapers.twitter import retrieve_tweets

ES_ENDPOINT = os.environ.get('ES_ENDPOINT')
ES_PORT = os.environ.get('ES_PORT')
API_KEY_MEANING_CLOUD = os.environ.get('API_KEY_MEANING_CLOUD')

print('ES connection: {} : {}'.format(ES_ENDPOINT, ES_PORT))


def get_amazon_id(url, regexes=[r"\/dp\/(.*)\/", r"\/product\/(.*)\/"]):
    amazon_id = None
    for regex in regexes:
        m = re.search(regex, url)
        if m and len(m.groups()) > 0:
            amazon_id = m.group(1)
            break
    return amazon_id


class ScrapyTask(luigi.Task):
    """
    Generates a local file containing 5 elements of data in JSON format.
    """

    #: the date parameter.

    #date = luigi.DateParameter(default=datetime.date.today())
    #field = str(random.randint(0,10000)) + datetime.datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
    
    url = luigi.Parameter()

    id = luigi.Parameter()

    website = luigi.Parameter()

    analysisType = luigi.Parameter()


    def run(self):
        """
        Writes data in JSON format into the task's output target.
        The data objects have the following attributes:
        * `_id` is the default Elasticsearch id field,
        * `text`: the text,
        * `date`: the day when the data was created.
        """
        #today = datetime.date.today()
        print(self.website, self.analysisType)
        filePath = '/tmp/_scrapy-%s.json' % self.id
        #scraperImported = imp.load_source(self.website, 'scrapers/%s.py' % (self.website))
        #scraperImported.startScraping(self.url, filePath)
        print(self.url, filePath)
        if self.website == 'reddit':
            print('###############################')
            print('---Reddit SEARCH API REQUEST---')
            print('###############################')
            #command= 'python myscript.py -a param={param}'.format(param=param)

        if self.website == 'amazon':
            amazon_id = get_amazon_id(self.url)
            domain = '.com' if 'amazon.com' in self.url else '.es' # TODO: Add an "else"
            command = 'scrapy runspider -a domain={domain} -a amazon_id={amazon_id} -a filePath={filePath} scrapers/spiders/{website}.py'.format(domain=domain,amazon_id=amazon_id,filePath=filePath,website=self.website)
            print(command)
            subprocess.call(command.split(), shell= False)   
        if self.website == 'twitter':
            retrieve_tweets(self.url, filePath, count=10)

        else:    
            command = 'scrapy runspider -a url={url} -a filePath={filePath} --nolog scrapers/spiders/{website}.py'.format(url=self.url,filePath=filePath,website=self.website)
            print(command)
            subprocess.call(command.split(), shell= False)    


    def output(self):
        """
        Returns the target output for this task.
        In this case, a successful execution of this task will create a file on the local filesystem.
        :return: the target output for this task.
        :rtype: object (:py:class:`luigi.target.Target`)
        """
        return luigi.LocalTarget(path='/tmp/_scrapy-%s.json' % self.id)




class AnalysisTask(luigi.Task):
    """
    Generates a local file containing 5 elements of data in JSON format.
    """

    #: the date parameter.

    #date = luigi.DateParameter(default=datetime.date.today())
    #field = str(random.randint(0,10000)) + datetime.datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
    
    url = luigi.Parameter()

    id = luigi.Parameter()

    website = luigi.Parameter()

    analysisType = luigi.Parameter()

    def requires(self):
        """
        This task's dependencies:
        * :py:class:`~.SenpyTask`
        :return: object (:py:class:`luigi.task.Task`)
        """
        return ScrapyTask(self.url, self.id, self.website, self.analysisType)


    def run(self):
        """
        Writes data in JSON format into the task's output target.
        The data objects have the following attributes:
        * `_id` is the default Elasticsearch id field,
        * `text`: the text,
        * `date`: the day when the data was created.
        """

        #today = datetime.date.today()
        if(self.website == 'reddit'):
            print('########################')
            print('ADD SENPY CODE')
            print('########################')
            #Recorrer JSON y añadir sentiment o emotion
            #Sentiment
            #review["sentiment"] = response_json["entries"][0]["sentiments"][0]["marl:hasPolarity"].split(":")[1]   
            #review["polarity"] = response_json["entries"][0]["sentiments"][0]["marl:polarityValue"]  
            #Emotion
            #review["emotion"] = response_json["entries"][0]["emotions"][0]["onyx:hasEmotion"]["onyx:hasEmotionCategory"].split("#")[1]
        if(self.website == 'twitter'):
            with self.output().open('w') as output:
                with self.input().open('r') as infile:
                    for line in infile:
                        i = json.loads(line)
                        if 'sentiments' in self.analysisType:
                            i["containsSentimentsAnalysis"] = True
                            r = requests.get('http://test.senpy.cluster.gsi.dit.upm.es/api/?algo=sentiment-meaningCloud&apiKey={}&i={}'.format(API_KEY_MEANING_CLOUD, i["text"])).json()
                            #i["analysis"] = response_json
                            time.sleep(0.51)
                            sentiments_arr = r["entries"][0]["sentiments"]
                            for x, sentiment in enumerate(sentiments_arr):
                                sentiment["@id"] = i["@id"]+"#Sentiment{num}".format(num=x)
                                sentiments_arr[x] = sentiment
                            #print(sentiments_arr) 
                            i["sentiments"] = sentiments_arr
                        if 'emotions' in self.analysisType:
                            i["containsEmotionsAnalysis"] = True
                            r = requests.get('http://test.senpy.cluster.gsi.dit.upm.es/api/?algo=emotion-anew&i=%s' % i["text"])
                            response = r.content.decode('utf-8')
                            try:
                                response_json = json.loads(response)
                                #i["analysis"] = response_json
                                emotions_arr = response_json["entries"][0]["emotions"]
                                for x, emotion in enumerate(emotions_arr):
                                    emotion["@id"] = i["@id"]+"#Emotion{num}".format(num=x)
                                    emotion['onyx:hasEmotion']["@id"] = i["@id"]+"#Emotion{num}".format(num=x)
                                    emotions_arr[x] = emotion
                                i["emotion"] = emotions_arr
                            except json.decoder.JSONDecodeError:
                                pass
                        if 'fake' in self.analysisType:
                            i["containsFakeAnalysis"] = True
                            probFake = 0.3
                            if random.random() < probFake:
                                i["fake"] = True
                            else: i["fake"] = False 
                        output.write(json.dumps(i))
                        #print(i)
                        output.write('\n')


        else:
            with self.output().open('w') as output:
                with self.input().open('r') as infile:
                    for line in infile:
                        attempts = 0
                        done = False
                        i = None
                        while not done:
                            try:
                                attempts += 1
                                i = json.loads(line)
                            except json.decoder.JSONDecodeError:
                                if attempts >= 3:
                                    print('ERROR decoding: {}'.format(line))
                                    continue
                        print(self.id)
                        i["id"] = str(self.id)
                        i["_id"] = i["id"]
                        #print(i["name"])
                        for review in i['reviews']:
                            if 'sentiments' in self.analysisType:
                                i["containsSentimentsAnalysis"] = True
                                r = requests.get('http://test.senpy.cluster.gsi.dit.upm.es/api/?algo=sentiment-meaningCloud&apiKey={}&i={}'.format(API_KEY_MEANING_CLOUD, review["reviewBody"]))
                                response = r.content.decode('utf-8')
                                try:
                                    response_json = json.loads(response)
                                    #i["analysis"] = response_json
                                    review["sentiment"] = response_json["entries"][0]["sentiments"][0]["marl:hasPolarity"].split(":")[1]   
                                    review["polarity"] = response_json["entries"][0]["sentiments"][0]["marl:polarityValue"]   
                                except json.decoder.JSONDecodeError:
                                    pass
                            if 'emotions' in self.analysisType:
                                i["containsEmotionsAnalysis"] = True
                                r = requests.get('http://test.senpy.cluster.gsi.dit.upm.es/api/?algo=emotion-anew&i=%s' % review["reviewBody"])
                                response = r.content.decode('utf-8')
                                try:
                                    response_json = json.loads(response)
                                    #i["analysis"] = response_json
                                    review["emotion"] = response_json["entries"][0]["emotions"][0]["onyx:hasEmotion"]["onyx:hasEmotionCategory"].split("#")[1]
                                except json.decoder.JSONDecodeError:
                                    pass
                            if 'fake' in self.analysisType:
                                i["containsFakeAnalysis"] = True
                                probFake = 0.3
                                if random.random() < probFake:
                                    review["fake"] = True
                                else: review["fake"] = False
                            output.write(json.dumps(i))
                            output.write('\n')

    def output(self):
        """
        Returns the target output for this task.
        In this case, a successful execution of this task will create a file on the local filesystem.
        :return: the target output for this task.
        :rtype: object (:py:class:`luigi.target.Target`)
        """
        return luigi.LocalTarget(path='/tmp/_analyzed-%s.json' % self.id)

class SemanticTask(luigi.Task):
    """
    Generates a local file containing 5 elements of data in JSON format.
    """

    #: the date parameter.

    #date = luigi.DateParameter(default=datetime.date.today())
    #field = str(random.randint(0,10000)) + datetime.datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
    
    url = luigi.Parameter()

    id = luigi.Parameter()

    website = luigi.Parameter()

    analysisType = luigi.Parameter()

    def requires(self):
        """
        This task's dependencies:
        * :py:class:`~.SenpyTask`
        :return: object (:py:class:`luigi.task.Task`)
        """
        return AnalysisTask(self.url, self.id, self.website, self.analysisType)


    def run(self):
        """
        Writes data in JSON format into the task's output target.
        The data objects have the following attributes:
        * `_id` is the default Elasticsearch id field,
        * `text`: the text,
        * `date`: the day when the data was created.
        """
        with self.output().open('w') as output:
            with self.input().open('r') as infile:
                for line in infile:
                    i = json.loads(line)
                    r = requests.get('http://model.dbpedia-spotlight.org/en/annotate?text=%s&confidence=0.2&support=20' % i["text"], headers={"Accept":"application/json"}).json()
                    entities_arr = r["Resources"]
                    for x, entity in enumerate(entities_arr):
                        entity["@id"] = i["@id"]+"#Entity{num}".format(num=x)
                        entities_arr[x] = entity
                    i["entities"] = entities_arr
                    output.write(json.dumps(i))
                    #print(i)
                    output.write('\n')


       
    def output(self):
        """
        Returns the target output for this task.
        In this case, a successful execution of this task will create a file on the local filesystem.
        :return: the target output for this task.
        :rtype: object (:py:class:`luigi.target.Target`)
        """
        return luigi.LocalTarget(path='/tmp/_semantic-%s.json' % self.id)


class FusekiTask(luigi.Task):
    """
    This task loads JSON data contained in a :py:class:`luigi.target.Target` and insert into Fuseki platform as a semantic 
    """
     #: date task parameter (default = today)
    url = luigi.Parameter()

    id = luigi.Parameter()

    website = luigi.Parameter()

    analysisType = luigi.Parameter()
    #file = str(random.randint(0,10000)) + datetime.datetime.now().strftime("%Y-%m-%d-%H-%M-%S")

    def requires(self):
        """
        This task's dependencies:
        * :py:class:`~.SenpyTask` 
        :return: object (:py:class:`luigi.task.Task`)
        """
        return SemanticTask(self.url, self.id, self.website, self.analysisType)

    def run(self):
        """
        Receive data from Senpy and is indexed in Fuseki
        """

        f = []

        with self.input().open('r') as infile:
            with self.output().open('w') as outfile:
                for i, line in enumerate(infile):
                    self.set_status_message("Lines read: %d" % i)
                    w = json.loads(line)
                    f.append(w)
                f = json.dumps(f)
                self.set_status_message("JSON created")
                #print(f)
                #g = Graph().parse(data=f, format='json-ld')
                r = requests.put('http://{fuseki}/gsicrawler/data'.format(fuseki=os.environ.get('FUSEKI_ENDPOINT_EXTERNAL')),
                    headers={'Content-Type':'application/ld+json'},
                    data=f)
                self.set_status_message("Data sent to fuseki")
                outfile.write(f)

    def output(self):
        """
        Returns the target output for this task.
        In this case, a successful execution of this task will create a file on the local filesystem.
        :return: the target output for this task.
        :rtype: object (:py:class:`luigi.target.Target`)
        """
        return luigi.LocalTarget(path='/tmp/_n3-%s.json' % self.id)



class Elasticsearch(CopyToIndex):
    """
    This task loads JSON data contained in a :py:class:`luigi.target.Target` into an ElasticSearch index.
    This task's input will the target returned by :py:meth:`~.Senpy.output`.
    This class uses :py:meth:`luigi.contrib.esindex.CopyToIndex.run`.
    After running this task you can run:
    .. code-block:: console
        $ curl "localhost:9200/example_index/_search?pretty"
    to see the indexed documents.
    To see the update log, run
    .. code-block:: console
        $ curl "localhost:9200/update_log/_search?q=target_index:example_index&pretty"
    To cleanup both indexes run:
    .. code-block:: console
        $ curl -XDELETE "localhost:9200/example_index"
        $ curl -XDELETE "localhost:9200/update_log/_query?q=target_index:example_index"
    """
    #: date task parameter (default = today)
    url = luigi.Parameter()

    id = luigi.Parameter()

    website = luigi.Parameter()

    analysisType = luigi.Parameter()

    #: the name of the index in ElasticSearch to be updated.
    index = luigi.Parameter()
    #: the name of the document type.
    doc_type = luigi.Parameter()
    #: the host running the ElasticSearch service.
    host = ES_ENDPOINT
    #: the port used by the ElasticSearch service.
    port = ES_PORT

    print(host,port)
    
    def requires(self):
        """
        This task's dependencies:
        * :py:class:`~.SenpyTask`
        :return: object (:py:class:`luigi.task.Task`)
        """
        return SemanticTask(self.url, self.id, self.website, self.analysisType)


class PipelineTask(luigi.Task):
  
    #: date task parameter (default = today)
    url = luigi.Parameter()

    id = luigi.Parameter()

    analysisType = luigi.Parameter()

    website = luigi.Parameter()

    #: the name of the index in ElasticSearch to be updated.
    index = luigi.Parameter()
    #: the name of the document type.
    doc_type = luigi.Parameter()
    #: the host running the ElasticSearch service.
    host = ES_ENDPOINT
    #: the port used by the ElasticSearch service.
    port = ES_PORT
   
    def requires(self):
        """
        This task's dependencies:
        * :py:class:`~.SenpyTask`
        :return: object (:py:class:`luigi.task.Task`)
        """

        yield FusekiTask(self.url, self.id, self.website, self.analysisType)
        
        index=self.index
        doc_type=self.doc_type

        yield Elasticsearch(self.url, self.id, self.website, self.analysisType, index, doc_type)

################################## REDDIT PIPELINE ##############################################

class FetchTaskReddit(luigi.Task):
    """
    Generates a local file containing 5 elements of data in JSON format.
    """

    #: the date parameter.

    #date = luigi.DateParameter(default=datetime.date.today())
    #field = str(random.randint(0,10000)) + datetime.datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
    
    url = luigi.Parameter()

    id = luigi.Parameter()

    website = luigi.Parameter()

    analysisType = luigi.Parameter()


    def run(self):
        """
        Writes data in JSON format into the task's output target.
        The data objects have the following attributes:
        * `_id` is the default Elasticsearch id field,
        * `text`: the text,
        * `date`: the day when the data was created.
        """


        filePathA = '/tmp/articles-%s.json' % self.id
        filePathC = '/tmp/comments-%s.json' % self.id
        #scraperImported = imp.load_source(self.website, 'scrapers/%s.py' % (self.website))
        #scraperImported.startScraping(self.url, filePath)
        #print(self.url, filePath)

        if self.website == 'reddit':
            #Get the articles
            scraperReddit.getArticles(search = self.url, limit = 10, filePath = filePathA)
            scraperReddit.getComments(articlesJSON = filePathA, filePath = filePathC)
            #Get the comments

        #print(command)
        #subprocess.call(command.split(), shell= False)    


    def output(self):
        """
        Returns the target output for this task.
        In this case, a successful execution of this task will create a file on the local filesystem.
        :return: the target output for this task.
        :rtype: object (:py:class:`luigi.target.Target`)
        """
        return [luigi.LocalTarget(path='/tmp/articles-%s.json' % self.id), luigi.LocalTarget(path='/tmp/comments-%s.json' % self.id)]

class AnalysisTaskGeneric(luigi.Task):
    """
    Generates a local file containing 5 elements of data in JSON format.
    """

    #: the date parameter.

    #date = luigi.DateParameter(default=datetime.date.today())
    #field = str(random.randint(0,10000)) + datetime.datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
    
    url = luigi.Parameter()

    id = luigi.Parameter()

    website = luigi.Parameter()

    analysisType = luigi.Parameter()
    output_file = luigi.Parameter()
    input_index = luigi.Parameter()
    analysis_field = luigi.Parameter(default='text')

    def requires(self):
        """
        This task's dependencies:
        * :py:class:`~.SenpyTask`
        :return: object (:py:class:`luigi.task.Task`)
        """
        return FetchTaskReddit(self.url, self.id, self.website, self.analysisType)


    def run(self):
        """
        Writes data in JSON format into the task's output target.
        The data objects have the following attributes:
        * `_id` is the default Elasticsearch id field,
        * `text`: the text,
        * `date`: the day when the data was created.
        """

        #today = datetime.date.today()

        with self.output().open('w') as output:
            with self.input()[self.input_index].open('r') as infile:
                for ix, lineAux in enumerate(infile):
                    self.set_status_message("Lines read: %d" % ix)
                    line = json.loads(lineAux)
                    line["id"] = str(self.id)
                    line["createdAt"] = line["id"]
                    text = line[self.analysis_field]
                    if 'sentiments' in self.analysisType:
                        r = requests.get('http://test.senpy.cluster.gsi.dit.upm.es/api/',
                                         params={'algo': 'sentiment-meaningCloud',
                                                 'apiKey': API_KEY_MEANING_CLOUD,
                                                 'i': text})
                        response = r.content.decode('utf-8')
                        try:
                            response_json = json.loads(response)
                            line["sentiments"] = response_json["entries"][0]["sentiments"]   
                        except (json.decoder.JSONDecodeError, KeyError) as ex:
                            print('Failed analysis of entry: {}'.format(ex))
                    if 'emotions' in self.analysisType:    
                        r = requests.get('http://test.senpy.cluster.gsi.dit.upm.es/api/',
                                        params={'algo': 'emotion-anew',
                                                'i': text})
                        response = r.content.decode('utf-8')
                        try:
                            response_json = json.loads(response)
                            line["emotions"] = response_json["entries"][0]["emotions"]
                        except (json.decoder.JSONDecodeError, KeyError) as ex:
                            print('Failed analysis of entry: {}'.format(ex))
                    output.write(json.dumps(line))
                    output.write('\n')


    def output(self):
        """
        Returns the target output for this task.
        In this case, a successful execution of this task will create a file on the local filesystem.
        :return: the target output for this task.
        :rtype: object (:py:class:`luigi.target.Target`)
        """
        return luigi.LocalTarget(path=self.output_file.format(self.id))

class AnalysisTaskArticles(AnalysisTaskGeneric):
    input_index = 0
    output_file = '/tmp/articles_analyzed-{}.json'
    analysis_field = 'title'

class AnalysisTaskComments(AnalysisTaskGeneric):
    input_index = 1
    output_file = '/tmp/comments_analyzed-{}.json'
    analysis_field = 'body'



class ElasticsearchPosts(CopyToIndex):
    """
    This task loads JSON data contained in a :py:class:`luigi.target.Target` into an ElasticSearch index.
    This task's input will the target returned by :py:meth:`~.Senpy.output`.
    This class uses :py:meth:`luigi.contrib.esindex.CopyToIndex.run`.
    After running this task you can run:
    .. code-block:: console
        $ curl "localhost:9200/example_index/_search?pretty"
    to see the indexed documents.
    To see the update log, run
    .. code-block:: console
        $ curl "localhost:9200/update_log/_search?q=target_index:example_index&pretty"
    To cleanup both indexes run:
    .. code-block:: console
        $ curl -XDELETE "localhost:9200/example_index"
        $ curl -XDELETE "localhost:9200/update_log/_query?q=target_index:example_index"
    """
    #: date task parameter (default = today)

    url = luigi.Parameter()

    id = luigi.Parameter()

    analysisType = luigi.Parameter()

    website = luigi.Parameter()

    #: the name of the index in ElasticSearch to be updated.
    index = luigi.Parameter()
    #: the name of the document type.
    doc_type = luigi.Parameter()
    #: the host running the ElasticSearch service.
    host = ES_ENDPOINT
    #: the port used by the ElasticSearch service.
    port = ES_PORT

    print(host,port)
    
    def requires(self):
        """
        This task's dependencies:
        * :py:class:`~.SenpyTask`
        :return: object (:py:class:`luigi.task.Task`)
        """
        return AnalysisTaskArticles(self.url, self.id, self.website, self.analysisType)

class ElasticsearchComments(CopyToIndex):
    """
    This task loads JSON data contained in a :py:class:`luigi.target.Target` into an ElasticSearch index.
    This task's input will the target returned by :py:meth:`~.Senpy.output`.
    This class uses :py:meth:`luigi.contrib.esindex.CopyToIndex.run`.
    After running this task you can run:
    .. code-block:: console
        $ curl "localhost:9200/example_index/_search?pretty"
    to see the indexed documents.
    To see the update log, run
    .. code-block:: console
        $ curl "localhost:9200/update_log/_search?q=target_index:example_index&pretty"
    To cleanup both indexes run:
    .. code-block:: console
        $ curl -XDELETE "localhost:9200/example_index"
        $ curl -XDELETE "localhost:9200/update_log/_query?q=target_index:example_index"
    """
    #: date task parameter (default = today)

    url = luigi.Parameter()

    id = luigi.Parameter()

    analysisType = luigi.Parameter()

    website = luigi.Parameter()

    #: the name of the index in ElasticSearch to be updated.
    index = luigi.Parameter()
    #: the name of the document type.
    doc_type = luigi.Parameter()
    #: the host running the ElasticSearch service.
    host = ES_ENDPOINT
    #: the port used by the ElasticSearch service.
    port = ES_PORT

    print(host,port)
    
    def requires(self):
        """
        This task's dependencies:
        * :py:class:`~.SenpyTask`
        :return: object (:py:class:`luigi.task.Task`)
        """
        return AnalysisTaskComments(self.url, self.id, self.website, self.analysisType)

class ElasticsearchReddit(luigi.WrapperTask):
    url = luigi.Parameter()
    id = luigi.Parameter()
    analysisType = luigi.Parameter()
    website = luigi.Parameter()
    #: the name of the index in ElasticSearch to be updated.
    index_Posts = luigi.Parameter()
    index_Comments = luigi.Parameter()
    #: the name of the document type.
    doc_type_Posts = luigi.Parameter()
    doc_type_Comments = luigi.Parameter()
    #: the host running the ElasticSearch service.
    host = ES_ENDPOINT
    #: the port used by the ElasticSearch service.
    port = ES_PORT

    def requires(self):
        #Task - Elasticsearch Posts
        index = self.index_Posts
        doc_type = self.doc_type_Posts
        yield ElasticsearchPosts(self.url, self.id, self.analysisType,self.website,index, doc_type)

        #Task - Elasticsearch - Comments
        index=self.index_Comments
        doc_type=self.doc_type_Comments
        yield ElasticsearchComments(self.url, self.id, self.analysisType,self.website,index,doc_type)

  
if __name__ == "__main__":
    #luigi.run(['--task', 'Elasticsearch'])
    luigi.run(    )
