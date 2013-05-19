#!/usr/bin/env python
#coding:utf-8
#
# Copyright 2007 Google Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
import webapp2
import os
import networkx as nx
from google.appengine.ext.webapp import template
from networkx.readwrite import json_graph
import xml.etree.ElementTree as ET
import json,re,urllib,urllib2

def cinii_search(query,result=[],start=0,limit=1000):
    api_key=""
    cinii_url="http://ci.nii.ac.jp/opensearch/search?count=200&format=rss&q="
    start=start
    query=query
    limit=limit
    urlquery=urllib.quote_plus(query)
    search_url=cinii_url+urlquery+"&start="+str(start)+api_key
    url=urllib2.urlopen(search_url)
    tree= ET.parse(url)
    root = tree.getroot()
    result=result
    result_number=int(root[0].find("{http://a9.com/-/spec/opensearch/1.1/}totalResults").text)
    start+=200
    result.append(root)
    if limit>start and result_number>start:
        cinii_search(query,result, start)
        # time.sleep(3)
    return result

def replacespace(wordlist):
    regex = re.compile(ur"[ 　]+")#空白文字列の削除
    regex2=re.compile(ur'[ア-ンa-zA-Z]')
    result=[re.sub(regex,"",i) for i in wordlist if re.match(regex2,i)==None]#カタカナ、アルファベットで始まる著者の除去
    return result

def cinii_export(ls):
    root=ls
    result=[]
    for k in root:
        for i in k.findall("{http://purl.org/rss/1.0/}item"):
            dic={}
            dic["title"]=i[0].text
            dic["author"]=replacespace([j.text for j in i.findall("{http://purl.org/dc/elements/1.1/}creator")])
            try:
                dic["publication"]=i.find("{http://prismstandard.org/namespaces/basic/2.0/}publicationName").text
            except:
                dic["publication"]=""
            try:
                dic["publicationdate"]=i.find("{http://prismstandard.org/namespaces/basic/2.0/}publicationDate").text
            except:
                dic["publicationdate"]=""
            dic["link"]=i.find("{http://purl.org/rss/1.0/}link").text
            try:
                dic["description"]=i.find("{http://purl.org/rss/1.0/}description").text
            except:
                dic["description"]=""
            result.append(dic)
    return result

def cinii_network(data):
    wd={}
    title=[]
    g=nx.Graph()
    authornumber=[]
    for i in data:
        if i["title"] not in title:#重複タイトルの除去
            title.append(i["title"])
            if len(i["author"])==1:#単著の場合
                authornumber.append(1)
                if i["author"][0] in wd.keys():
                    wd[i["author"][0]]+=1
                    g.node[i["author"][0]]["viz"]["size"]+=1
                else:
                    g.add_node(i["author"][0],viz={"size":1})
                    wd[i["author"][0]]=1
            else:#共著の場合
                counter=0
                for j in range(len(i["author"])):
                    counter+=1
                    if i["author"][j] in wd.keys():
                        wd[i["author"][j]]+=1
                        g.node[i["author"][j]]["viz"]["size"]+=1
                    else:
                        g.add_node(i["author"][j],viz={"size":1})
                        wd[i["author"][j]]=1
                    for k in i["author"][j:]:
                        if i["author"][j]!=k :
                            if k in g.edge[i["author"][j]]:
                                g.edge[i["author"][j]][k]["weight"]+=1
                            else:
                                g.add_edge(i["author"][j],k,weight=1)
                authornumber.append(counter)
    return [g,title,authornumber,wd]

def networkanalysis(g,authornumber,wd):
    g=g
    authornumber=authornumber
    wd=wd
    a=0.0
    authorcount={}
    articlenumber=[]
    for k,v in sorted(wd.items(),key=lambda x:x[1], reverse=True)[0:3]:
        articlenumber.append({"author":k,"val":v})
    for i in authornumber:
        a+=i
        if authorcount.has_key(i):
            authorcount[i]+=1
        else:
            authorcount[i]=1
    means=round(a/len(authornumber),2)
    mode={}
    coauthornumber=[]
    for k,v in sorted(authorcount.items(),key=lambda x:x[1],reverse=True)[0:1]:
        mode["mode"]=k
        mode["val"]=v
    if len(authornumber)%2==0:  
        midian=(authornumber[len(authornumber)/2-1]+authornumber[len(authornumber)/2])/2
    else:
        midian=authornumber[(len(authornumber)-1)/2]
    for k,v in sorted(g.degree().items(),key=lambda x:x[1],reverse=True)[0:3]:
        coauthornumber.append({"author":k,"coauthornum":v})
    return articlenumber,means,mode,midian,coauthornumber


class MainPage(webapp2.RequestHandler):


    def get(self):    
        params={"words":"","json":"","searchresult":"","articlenumber":"","means":"","mode":"","midian":"","coauthornumber":""}
        fpath = os.path.join(os.path.dirname(__file__),'index.html')
        html = template.render(fpath,params)
        self.response.headers['Content-Type'] = 'text/html'
        self.response.out.write(html)
    def post(self):
        query=self.request.get("words").encode("utf-8")
        data=cinii_export(cinii_search(query,result=[]))
        g,title,authornumber,wd=cinii_network(data)
        articlenumber,means,mode,midian,coauthornumber=networkanalysis(g,authornumber,wd)
        for i in g.nodes():
            if (len(g.edge[i])<2 and g.node[i]["viz"]["size"]<2):
                g.remove_node(i)
        jsondata = json_graph.node_link_data(g)
        jsondata=json.dumps(jsondata,ensure_ascii=False)
        params = {"words":query,"json":jsondata,"searchresult":len(title),"articlenumber":articlenumber,"means":means,"mode":mode,"midian":midian,"coauthornumber":coauthornumber}
        fpath = os.path.join(os.path.dirname(__file__),'index.html')
        html = template.render(fpath,params)
        self.response.headers['Content-Type'] = 'text/html'
        self.response.out.write(html)



app = webapp2.WSGIApplication([
    ('/', MainPage)
], debug=True)
