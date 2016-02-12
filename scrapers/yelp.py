import os

def startScraping(url, resultPath):
	scriptPath = os.getcwd()+'/scrapers/spiders/YelpScraper.py'
	params = '-a url="%s" -a filePath="%s" --nolog' % (url, resultPath)
	os.system('scrapy runspider %s %s' %(scriptPath, params))