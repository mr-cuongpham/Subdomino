#!/usr/bin/python
# -*- coding: utf-8 -*-
import time
import re
import os
import sys
import argparse
import socket
import requests
import signal
import multiprocessing
from ping import *
from subdomain_scan import *
from subdomain_interpreter import *
from multiprocessing import Process, Pool

# Initialize the global variable
def init_enumeration(is_nmap):
	# Storing all the subdomains
	global online_subdmn
	online_subdmn = []

	# Handle nmap scan for every subdomain 
	# Using global variable because of the signal handler
	global nmap
	if (is_nmap):
		print "[OPTION] Nmap Scan enabled"
	else:
		print "[OPTION] Nmap Scan disabled"
	nmap = is_nmap

# Multiprocessing ping scan
def multiprocessing_ping_scan(host,n_iter,n_max):
	try:
		if scan_subdomain(host):
			print "n° {:>4}/{} - \033[92mUP - \033[0m{}".format(n_iter, n_max, host)
			return host
		else:
			return None

	except KeyboardInterrupt,e:
		return None

# Generate a list of potential subdomain
def brute_with_file(names_file,domain, process):
	print "\n[+] Brute subdomain from {} with {} pools...".format(names_file, process)
	global online_subdmn

	# Subdomain extensions are stored in names.txt
	with open(names_file,'r') as dict_file:
		dict_file = dict_file.readlines()

		pool = Pool(process)

		# Multiprocessing
		max_subdmn = len(dict_file)
		for index,subdmn in enumerate(dict_file):
			pool.apply_async(multiprocessing_ping_scan, ("http://"+subdmn.strip()+"."+domain, index, max_subdmn), callback=online_subdmn.append)
    	
    	# We need this to stop it with Ctrl+C
		try:
			time.sleep(10)
			pool.close()
			pool.join()

		except KeyboardInterrupt:
			print " Multiprocessing stopped!"
			pool.terminate()
			pool.join()


# Function for the multiprocessing crawl
def crawl_website_for_subdomain_extract(stuff_to_get):
	stuff_got = []

	# Use an User-Agent to avoid a ban from Google
	headers = {
		'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/53.0.2785.101 Safari/537.36 OPR/40.0.2308.52 (Edition beta)'	
	}
	resp = requests.get(stuff_to_get, headers=headers).text

	# Ban detection
	if 'Our systems have detected unusual traffic' in resp:
		print "Too many requests, Google blocked us :X"
	else:
		stuff_got.append(resp.encode('utf-8'))

	return "".join(stuff_got)

# Extract subdomain from google results
def crawl_google_for_subdomain(is_google,domain,process):
	if (is_google):
		print "\n[OPTION] Google Scan enabled"
		print "[+] Crawl from Google..."
		global online_subdmn
		
		# Set a google URL for the multithread
		google = 'https://www.google.co.th/search?q=site:*.{} -www.{}&start='.format(domain,domain)

		# Define number of results
		stuff_that_needs_getting = []
		for i in range(0,is_google):
			stuff_that_needs_getting.append(google+str(i*10))

		# Use multi threads
		pool = multiprocessing.Pool(process)
		pool_outputs = pool.map(crawl_website_for_subdomain_extract, stuff_that_needs_getting) #function, arg(=list of hosts)
		pool.close()
		pool.join()

		# Threads are done, now let parse theirs results
		google_source = "".join(pool_outputs)
		regex = re.compile(r'<cite.*?>([^\'" <>]+)<\/cite>')
		websites = regex.findall(google_source)

		for website in websites:
			clean_url = ""
					
			# Handle result like bla.domain
			if(not "http" in website):
				clean_url = "http://" + website
				clean_url = '/'.join(clean_url.split('/',3)[:-1])

			# Handle result like http://bla.domain
			else:
				clean_url = '/'.join(website.split('/',3)[:-1])

			if(not clean_url in online_subdmn):
				online_subdmn.append(clean_url)
				print "\033[92mFound - \033[0m" + clean_url
			
		pool.terminate()
	else:
		print "[OPTION] Google Scan disabled"

# Extract subdomain from yahoo results
def crawl_yahoo_for_subdomain(is_yahoo,domain,process):
	if (is_yahoo):
		print "\n[OPTION] Yahoo Scan enabled"
		print "[+] Crawl from Yahoo..."
		global online_subdmn

		# Set a google URL for the multithread
		yahoo = 'https://search.yahoo.com/search?p=site%3A{}+-www.{}&b='.format(domain,domain)

		# Define number of results
		stuff_that_needs_getting = []
		for i in range(0,is_yahoo):
			stuff_that_needs_getting.append(yahoo+str(i*10))

		# Use multi threads
		pool = multiprocessing.Pool(process)
		pool_outputs = pool.map(crawl_website_for_subdomain_extract, stuff_that_needs_getting) #function, arg(=list of hosts)
		pool.close()
		pool.join()

		# Threads are done, now let parse theirs results
		yahoo_source = "".join(pool_outputs)
		regex = re.compile(r'href="(.*?'+domain+'.*?)" referrerpolicy="origin"')
		websites = regex.findall(yahoo_source)

		for website in websites:
			clean_url = ""
					
			# Handle result like bla.domain
			if(not "http" in website):
				clean_url = "http://" + website
				clean_url = '/'.join(clean_url.split('/',3)[:-1])

			# Handle result like http://bla.domain
			else:
				clean_url = '/'.join(website.split('/',3)[:-1])

			if(not clean_url in online_subdmn and domain in clean_url):
				online_subdmn.append(clean_url)
				print "\033[92mFound - \033[0m" + clean_url
			
		pool.terminate()
	else:
		print "[OPTION] Yahoo Scan disabled"

	print online_subdmn


# Generating a report for every subdomain
def generate_reports():
	global online_subdmn
	print "\n[+] Generating subdomain's report"

	# Create the directory
	if not os.path.exists('reports'):
		os.mkdir('reports',0755)

	# Save subdomain's list
	with open('reports/subdomains.lst','w+') as f:
		f.write("\n".join(online_subdmn))
	print "\n[+] Exported in subdomain.lst"

	# One report for every subdomains - if nmap option enabled
	global nmap
	if nmap == True:
		for subdmn in online_subdmn:
			path = "reports/"+subdmn.replace('://','_')
			if not os.path.exists(path):
				open(path,'w+')

# Last function save everything
def end_of_software():
	try:
		# Sort the list for a clean output
		global online_subdmn
		online_subdmn = filter(None, online_subdmn)
		online_subdmn = sorted(online_subdmn)
		print "\n[+] Subdomains founds : ",online_subdmn

		# Start a report for every subdomain
		generate_reports()

		# Launch NMAP if necessary
		nmap_subdomains(online_subdmn, nmap)

		# Rule Interpreter
		interpreter = Interpreter(online_subdmn)
		interpreter.launch_scans()

		# Exit the soft
		exit(0)

	except KeyboardInterrupt:
		print "Happy Hunting ! :)"
		exit()