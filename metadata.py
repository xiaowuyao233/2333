#coding:utf-8
import sys
reload(sys)
sys.setdefaultencoding('utf-8')

import os
import requests
import urllib
import traceback
import pygeoip
import threading
import socket
import sys
import hashlib
import datetime
import time
import json
import re
import metautils
from bencode import bencode, bdecode
geoip = pygeoip.GeoIP('GeoIP.dat')




def decode(encoding, s):
    if type(s) is list:
        s = ';'.join(s)
    u = s
    for x in (encoding, 'utf8', 'gbk', 'big5'):
        try:
            u = s.decode(x)
            return u
        except:
            pass
    return s.decode(encoding, 'ignore')

def decode_utf8(encoding, d, i):
    if i+'.utf-8' in d:
        return d[i+'.utf-8'].decode('utf8')
    return decode(encoding, d[i])

def parse_metadata(data):
    info = {}
    encoding = 'utf8'
    try:
        torrent = bdecode(data)
        if not torrent.get('name'):
            return None
    except:
        return None
    try:
        info['create_time'] = datetime.datetime.fromtimestamp(float(torrent['creation date']))+ datetime.timedelta(hours=8)
    except:
        info['create_time'] = datetime.datetime.utcnow()+ datetime.timedelta(hours=8)

    if torrent.get('encoding'):
        encoding = torrent['encoding']
    if torrent.get('announce'):
        info['announce'] = decode_utf8(encoding, torrent, 'announce')
    if torrent.get('comment'):
        info['comment'] = decode_utf8(encoding, torrent, 'comment')[:200]
    if torrent.get('publisher-url'):
        info['publisher-url'] = decode_utf8(encoding, torrent, 'publisher-url')
    if torrent.get('publisher'):
        info['publisher'] = decode_utf8(encoding, torrent, 'publisher')
    if torrent.get('created by'):
        info['creator'] = decode_utf8(encoding, torrent, 'created by')[:15]

    if 'info' in torrent:
        detail = torrent['info'] 
    else:
        detail = torrent
    info['name'] = decode_utf8(encoding, detail, 'name')
    if 'files' in detail:
        info['files'] = []
        for x in detail['files']:
            if 'path.utf-8' in x:
                v = {'path': decode(encoding, '/'.join(x['path.utf-8'])), 'length': x['length']}
            else:
                v = {'path': decode(encoding, '/'.join(x['path'])), 'length': x['length']}
            if 'filehash' in x:
                v['filehash'] = x['filehash'].encode('hex')
            info['files'].append(v)
        info['length'] = sum([x['length'] for x in info['files']])
    else:
        info['length'] = detail['length']
    info['data_hash'] = hashlib.md5(detail['pieces']).hexdigest()
    if 'profiles' in detail:
        info['profiles'] = detail['profiles']
    return info


def save_metadata(dbcurr, binhash, address, start_time, data):
    utcnow = datetime.datetime.utcnow()
    name = threading.currentThread().getName()
    try:
        info = parse_metadata(data)
        if not info:
            return
    except:
        traceback.print_exc()
        return
    info_hash = binhash.encode('hex')
    info['info_hash'] = info_hash
    # need to build tags
    info['tagged'] = False
    info['classified'] = False
    info['requests'] = 1
    info['last_seen'] = utcnow+ datetime.timedelta(hours=8)
    info['source_ip'] = address[0]
	

    if info.get('files'):
        files = [z for z in info['files'] if not z['path'].startswith('_')]
        if not files:
            files = info['files']
    else:
        files = [{'path': info['name'], 'length': info['length']}]
    files.sort(key=lambda z:z['length'], reverse=True)
    bigfname = files[0]['path']
    info['extension'] = metautils.get_extension(bigfname).lower()
    info['category'] = metautils.get_category(info['extension'])

	
    if 'files' in info:
        try:
            dbcurr.execute('INSERT  INTO search_filelist VALUES(%s, %s)', (info['info_hash'], json.dumps(info['files'])))
        except:
            print name, u'insert error', sys.exc_info()[1]
        del info['files']

    if info['category'] not in [u'影视',u'音乐',u'图像',u'文档书籍']:
        pass
    #elif not re.findall(ur"[\u4e00-\u9fa5]+",info['name']):
    #    pass
    #只入库中文资源
    else:
        try:
            try:
                print '\n', (datetime.datetime.utcnow()+ datetime.timedelta(hours=8)).strftime("%Y-%m-%d %H:%M:%S"),u'分类:',info['category'], u'Hash值:',info['info_hash'],u'文件名:', info['name'], u'格式:', info['extension'], u'IP地址:',address[0],u'地区:', geoip.country_name_by_addr(address[0]),u'保存成功!'
            except:
                print '\n',(datetime.datetime.utcnow()+ datetime.timedelta(hours=8)).strftime("%Y-%m-%d %H:%M:%S"), u'insert error', info['info_hash'], sys.exc_info()[1]
            ret = dbcurr.execute('INSERT INTO search_hash(info_hash,category,data_hash,name,extension,classified,source_ip,tagged,' + 
       'length,create_time,last_seen,requests,comment,creator) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)',
            (info['info_hash'], info['category'], info['data_hash'], info['name'], info['extension'], info['classified'],
            info['source_ip'], info['tagged'], info['length'], info['create_time'], info['last_seen'], info['requests'],
            info.get('comment',''), info.get('creator','')))
            dbcurr.connection.commit()
        except:
            print name, u'insert error', info
            traceback.print_exc()
            return
