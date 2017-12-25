#  * ---------------------------------------------------------------------
#  *  Author        : Julio Carranza
#  *  Name          : rsvpint-w-bypass.py
#  *  Version       : 1.00, 2016-10-24

#  *
#  *  Last Modified : 2016-10-24
#  *  Description   : Intent of the script is to calculate the bw
#  *                  that bypass path would use in case the 
#  *                  primary path of the LSPs that are protecting
#  *                  fail. For that find all bypass traversing the 
#  *                  router. It calculates the bw of each bypass
#  *                  as the sum of the bw of al the LSPs that is
#  *                  protecting. Finally, checks the egress 
#  *                  interface for each bypass and adds it to the
#  *                  bypass bw for the corresponding rsvp 
#  *                  interface. It will print the reserved bandwidth
#  *                  the bypass bw that is the sum of all bypass
#  *                  paths, and the sum of both. The script has 
#  *                  options for debugging: --l shows lsp with its
#  *				  bypass, --b shows bypass with a list of LSP
#  *				  protecting and --i shows the bypass in a rsvp 
#  *				  interface.
#  *
#  *  installation  : PyEZ library is required for installation and
#  *				  requirements, refer to:  
#  *                  www.juniper.net/techpubs/en_US/junos-pyez1.0/
#  *                  topics/task/installation/
#  *                  junos-pyez-server-installing.html
#  *
#  *  Caveat        : The script doesn't have into account the bw
#  *                  for the transit bypass. Bypass don't carry 
#  *                  bw information, and router don't have
#  *                  information of the LSPs protected by the 
#  *                  transit bypass. BW calculation is incomplete
#  *                  for core routers.
#  *


from jnpr.junos import Device
from getpass import getpass
from lxml import etree
import re, argparse

#parsing argument to the program
parser = argparse.ArgumentParser(description=
	'Calculate the bw used by bypass lsps in a int')
parser.add_argument('device', 
    help='device IP address' )
parser.add_argument('user', 
    help='user used to login to device' )
parser.add_argument('--l',
    action='store_true',
    help='shows lsp with bypass and bw' )
parser.add_argument('--b',
    action='store_true',
    help='shows bypass with lsps protecting and total bw for it' )
parser.add_argument('--i',
    action='store_true',
    help='shows detailed output with bypass lsps in the interface' )

args = parser.parse_args()	
passwd=getpass()

#Convert bw in K/M/Gbps to intenger
def xbpstobps(xbps, bps):
	if re.match('0bps', xbps):
		bps += 0
	elif re.match('.*(kbps)', xbps):
		bw = xbps.split('kbps')
		bps += float(bw[0])*1000
	elif re.match('.*(Mbps)', xbps):
		bw = xbps.split('Mbps')
		bps+= float(bw[0])*1000000
	elif re.match('.*(Gbps)', xbps):
		bw = xbps.split('Gbps')
		bps += float(bw[0])*1000000
	else:
		print "Only 0bps, kbps, Mbps, Gbps is coded. It can't convert " + xbps
	return int(bps)

#Convert the intenger bw to the K/M/Gbps
def inttobps(intbps):
	if intbps > 1000000000:
		xbps = float(intbps)/1000000000
		if ( intbps %1000000000 == 0):
			xbps = int(xbps)
		textbps = str(xbps) + 'Gbps'
	elif intbps > 1000000:
		xbps = float(intbps)/1000000
		if ( intbps %1000000 == 0):
			xbps = int(xbps)
		textbps = str(xbps) + 'Mbps'
	elif intbps > 1000:
		xbps = float(intbps)/1000
		if ( intbps %1000 == 0):
			xbps = int(xbps)
		textbps = str(xbps) + 'Kbps'
	else:
		textbps = str(intbps) + 'bps'
	return textbps


#Opening NETCONF session 
r0 = Device(host=args.device,user=args.user,password=passwd,normalize=True)
r0.open()

#XML outputs required to perform computation
mpls_lsp = r0.rpc.get_mpls_lsp_information(extensive = True)
rsvp_session = r0.rpc.get_rsvp_session_information(extensive = True)
rsvp_interface = r0.rpc.get_rsvp_interface_information()

#Closing NETCONF session
r0.close()

#Obtain all LSPs that have an active bypass path
lsptype =[ 'Ingress', 'Transit']
lsps ={}
for t in lsptype:
	lsplist = rsvp_session.findall("rsvp-session-data[session-type='"+t+"']/rsvp-session[is-nodeprotection]/name")
	for lsp in lsplist:
		lsp = lsp.text
		lsps[lsp] = {}
		lsps[lsp]['type'] = t
		
#Store LSP and its bypass path in a dictionary
bypasslist ={}
for lsp in lsps:
	lsps[lsp]['bypass'] = rsvp_session.find("rsvp-session-data/rsvp-session[name='"+lsp+"']/bypass-name")
	lsps[lsp]['bypass'] = lsps[lsp]['bypass'].text
	lsps[lsp]['bw'] = mpls_lsp.find("rsvp-session-data/rsvp-session/mpls-lsp[name='"+lsp+"']/mpls-lsp-path/bandwidth")
	lsps[lsp]['bw'] = lsps[lsp]['bw'].text
	#Print LSP with its bypass if l is True
	if args.l:
		print lsp + " bypass name: " + lsps[lsp]['bypass'] + " bandwidth: " + lsps[lsp]['bw']

	#Store bypass path with all the LSPs protecting in a dictionary
	if not lsps[lsp]['bypass'] in bypasslist:	
		bypasslist[lsps[lsp]['bypass']] = {}
		bypasslist[lsps[lsp]['bypass']]['list'] = []
		bypasslist[lsps[lsp]['bypass']]['bw'] = 0		
	bypasslist[lsps[lsp]['bypass']]['list'].append(lsp)
	bypasslist[lsps[lsp]['bypass']]['bw'] = xbpstobps((lsps[lsp]['bw']), bypasslist[lsps[lsp]['bypass']]['bw'])

#Print bypass with list of LSPs protecting if b is True
if args.b:
	for bypass in bypasslist:
		print "bypass: " + bypass + " bw: " + str(bypasslist[bypass]['bw']) + " lsps: " + str(bypasslist[bypass]['list'])

#Find RSVP interfaces and bypass on them
rsvpinterfaces = rsvp_interface.findall("rsvp-interface/interface-name")
rsvpif = {}
for ri in rsvpinterfaces:
	if (ri.text != 'lo0.0'):
		rsvpif[ri.text] ={}
		rsvpif[ri.text]['bypasslist'] = []
		reservedbw =  rsvp_interface.find("rsvp-interface[interface-name='"+ri.text+"']/rsvp-telink/total-reserved-bandwidth")
		rsvpif[ri.text]['reservedbw'] = reservedbw.text
		bypassinif = rsvp_session.xpath("rsvp-session-data[session-type='Ingress']/rsvp-session[starts-with(name, 'Bypass-')]/packet-information[@heading='  PATH'][interface-name='"+ri.text+"']")
		bp = []
		bpbw = 0
		for i in bypassinif:
			bp.append((i.find("../name")).text)
			bpbw += bypasslist[(i.find("../name")).text]['bw']
		if args.i:
			print "interface: " + ri.text + " reserved: " + rsvpif[ri.text]['reservedbw'] +  " bypass_list: " + str(bp) + " bypass_bw: " + inttobps(bpbw) +" total: " + inttobps(xbpstobps((rsvpif[ri.text]['reservedbw']), 0) + bpbw  )
		else:
			print "interface: " + ri.text + " reserved: " + rsvpif[ri.text]['reservedbw'] +  " bypass_bw: " + inttobps(bpbw) +" total: " + inttobps(xbpstobps((rsvpif[ri.text]['reservedbw']), 0) + bpbw  )


