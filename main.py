# from PyPDF2 import PdfReader
# import openai
# Importing flask module in the project is mandatory
# An object of Flask class is our WSGI application.
from flask import Flask
from flask import jsonify
from flask import request
from PyPDF2 import PdfReader
from dotenv import load_dotenv
from waitress import serve
import openai
import os 

app = Flask(__name__)

#fill in your api key here
load_dotenv()
openai.api_key = os.getenv('OPENAPI_KEY')

#Takes a PDF file and extract each page's text. Returns a list with text from each page
def extractText(filename):
    reader = PdfReader(filename)
    number_of_pages = len(reader.pages)
    pageList = [""] * number_of_pages
    for i in range(number_of_pages):
        text_body = reader.pages[i].extract_text().lower()
        text_body = text_body.replace(' ', '')
        pageList[i] = text_body
    return pageList

#Using the extracted text, parse/return the methodology, results, and discussion
def extractSections(pageList):
    #merge all pages into one string
    fullText = ""
    for page in pageList:
        fullText += page
    #try to find the common sections that can be found in all papers 
    methodsStartInd = fullText.find('andmethods\n') + 10
    resultStartInd = fullText[methodsStartInd: ].find('results\n') + methodsStartInd + 7
    discussionStartInd = fullText[resultStartInd: ].find('discussion\n') + resultStartInd + 10
    referencesStartInd = fullText[discussionStartInd: ].find('references') + discussionStartInd + 10
    methods = fullText[methodsStartInd: resultStartInd]
    results = fullText[resultStartInd: discussionStartInd]
    discussion = fullText[discussionStartInd: referencesStartInd]
    return {"methods": methods, "results": results[:3882] if len(results) > 3882 else results, "discussion": discussion[:3882] if len(discussion) > 3882 else discussion}

#query openai
def query(sysPrompt, userPrompt):
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        temperature= 0, #This minimizes randomness in response
        messages=[
            {"role": "system", "content": f"{sysPrompt}"},
            {"role": "user", "content": f"{userPrompt}"},
            ],
        )
    return(response["choices"][0]["message"]["content"])

def getFirstPage(pageList):
    for page in pageList:
        if page != "":
            return page[:3979] if len(page) > 3979 else page

#Listen to POST API calls. Expects a pdf file, and will send back data about features
@app.route('/upload', methods=['POST'])
def process_Pdf():
    #Fetch file from request, save it in local files
    file = request.files['study']
    filename = file.filename
    file.save(filename)
    #Extract text from saved file, then pick out important parts of the paper, like results and discussion
    pages = extractText(filename)
    sections = extractSections(pages)
    firstPage = getFirstPage(pages)
    #Prompt GPT model for key features by feeding it the sections the information is most likely to be in

    #Start with title, author, and abstract
    sysPrompt1 =  f"You are a helpful research assistant. This is the first page of an academic paper {firstPage}"
    userPrompt1 = f"Paper name: ? Authors: ? Abstract: ? Publication Year: ?" #This prompt gives us a predictable and parsable response 
    res1 = query(sysPrompt1, userPrompt1)
    #Parse info from GPT response
    temp = res1.split('\n')
    title = temp[0].replace("Paper name: ", "")
    authors = temp[1].replace("Authors: ", "")
    abstract = temp[2].replace("Abstract: ", "")
    year = temp[3].replace("Publication Year: ", "")

    #Next is to analyze results for methodology, conclusion, study size, study duration, strength of data
    sysPrompt2 =  f"You are a helpful research assistant. This is the results of an academic paper {sections['results']}"
    userPrompt2 = f"As briefly as possibe, answer the following. Experiment Methodology: ? Conclusion: ? Study Size: ? Study Duration: ? Strength of data: ?" #This prompt gives us a predictable and parsable response 

    res2 = query(sysPrompt2, userPrompt2)
    temp = res2.split('\n')
    temp = [i for i in temp if i != ""]
    methodology = temp[0].replace("Experiment Methodology: ", "")
    conclusion = temp[1].replace("Conclusion: ", "")
    size = temp[2].replace("Study Size: ", "")
    duration = temp[3].replace("Study Duration: ", "")
    strength = temp[4].replace("Strength of data: ", "")

    #Examine discussion for weaknesses in study
    sysPrompt3 =  f"You are a helpful research assistant. This is the discussion of an academic paper {sections['discussion']}"
    userPrompt3 = f"In bullets, give study's weaknesses"
    weaknesses = query(sysPrompt3, userPrompt3).split("\n")

    data = {"title": title, "year": year, "authors": authors, "abstract": abstract, "method": methodology, "conclusion": conclusion, "size": size, "duration": duration, "strength": strength, "weaknesses": weaknesses}
    response = jsonify(response=data, status=200, mimetype='application/json')
    response.headers.add('Access-Control-Allow-Origin', '*')
    return response

@app.route('/')
def index():
    return 'Hello World'
    
# main driver function
if __name__ == '__main__':

    serve(app, host='127.0.0.1', port=5000, threads=2)