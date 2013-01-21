#!/usr/bin/python
"""Scan directory and for each subdirectory create tgz file if any file has changed since last archivization

Example content of metadata file:

```
<?xml version="1.0" encoding="UTF-8" standalone="no" ?>
<archive version='1'>
<directory name='dir1' lastArchivized='2011-02-03 18:34:54 GMT' />
</archive>
```

#### License

Copyright (C) 2007 Kamil Demecki <kodstark@gmail.com>

Licensed under the terms of any of the following licenses at your choice:

- GNU Lesser General Public License Version 2.1 or later (the "LGPL")
  http://www.gnu.org/licenses/lgpl.html

- Mozilla Public License Version 1.1 or later (the "MPL")
  http://www.mozilla.org/MPL/MPL-1.1.html
"""
import os
import time
import tarfile
import calendar
import xml.parsers.expat
import xml.dom.minidom

def parse_archive_history():    
    result = {}
    try:
        dir_nodes = get_dir_nodes()
        for dir_node in dir_nodes:
            parse_dir_node(dir_node, result)
    except IOError:
        pass
    except xml.parsers.expat.ExpatError as ex:
        raise ExcInvalidFormat('Invalid format archive-history.xml - ' + str(ex))
    return result

def get_dir_nodes():
    archive_dom = xml.dom.minidom.parse('archive-history.xml')
    root_elements = archive_dom.childNodes
    assert_root_elements(root_elements)
    archiveElement = root_elements[0]
    version = archiveElement.getAttribute('version')
    assert_version(version)
    dir_nodes = [node for node in archiveElement.childNodes if node.nodeName == 'directory']
    return dir_nodes

def assert_root_elements(root_elements):
    if len(root_elements) != 1:
        raise ExcInvalidFormat('Invalid root elements <archive> in metadata file')

def assert_version(version):
    if not version:
        raise ExcInvalidFormat('Lack of version attribute in metadata file')

def assert_dir_name(dir_name, dir_node):
    if not dir_name:
        raise ExcInvalidFormat('Missing name attribute for directory ' + str(dir_node))

def assert_last_archivized(last_archivized_str, dir_node):
    if not last_archivized_str:
        raise ExcInvalidFormat('Missing lastArchivized attribute for directory ' + str(dir_node))

def get_last_archivized(dir_node):
    last_archivized_str = dir_node.getAttribute('lastArchivized')
    assert_last_archivized(last_archivized_str, dir_node)
    last_archivized_str = dir_node.getAttribute('lastArchivized')
    try:
        last_archivized = calendar.timegm(time.strptime(last_archivized_str, '%Y-%m-%d %H:%M:%S GMT'))
    except ValueError as ex:
        raise ExcInvalidFormat('Invalid value [%s] for attribute lastArchivized %s' % (last_archivized_str, ex))
    return last_archivized

def parse_dir_node(dir_node, history):
    dirName = dir_node.getAttribute('name')
    assert_dir_name(dirName, dir_node)
    last_archivized = get_last_archivized(dir_node)
    history[dirName] = last_archivized

def update_archives(directory, history):
    sub_dirs = get_sub_dirs(directory)
    for sub_dir in sub_dirs:
        archive_name = get_archive_name(sub_dir)
        try:
            try_archive(sub_dir, archive_name, history)            
        except KeyboardInterrupt:
            print 'Interrupt creating %s' % archive_name
            break
        except Exception as ex:
            print "Error in creating %s - %s" %(archive_name, ex)
            break   
    return history   

def get_sub_dirs(directory):
    result = [curDir for curDir in os.listdir(directory) if os.path.isdir(os.path.join(directory, curDir))]
    return result

def get_archive_name(sub_dir):
    tarName = 'z-backup-%s.tar.gz' % sub_dir
    return tarName

def try_archive(sub_dir, archive_name, history):
    last_archivized_time, last_archivized_time_str = get_last_archivized_time(sub_dir, history)
    print '## Dir %-30s %s last processed' % (sub_dir, last_archivized_time_str)
    isModified = is_modified_after(sub_dir, last_archivized_time)
    if isModified:
        print '---- Creating archive %s' % archive_name
        create_archive(sub_dir, archive_name, history)
        
def get_last_archivized_time(sub_dir, history):
    if sub_dir in history:
        last_archivized_time = history[sub_dir]
    else:
        last_archivized_time = -1
    if last_archivized_time >= 0:
        last_archivized_time_str = sec_to_str_time(last_archivized_time)
    else:
        last_archivized_time_str = 'never'
    return last_archivized_time, last_archivized_time_str        
        
def is_modified_after(directory, max_mtime):    
    for curdir, dirs, files in os.walk(directory):
        file_mtime = os.path.getmtime(curdir)
        if (file_mtime > max_mtime):
            print '---- Dir %s was modified'  % curdir
            return file_mtime        
        for fname in files:
            file_mtime = os.path.getmtime(os.path.join(curdir, fname))
            if (file_mtime > max_mtime):
                print '---- File %s was modified'  % os.path.join(curdir, fname)
                return file_mtime
        if 'CVS' in dirs: dirs.remove('CVS')
        if '.svn' in dirs: dirs.remove('.svn')
    return None        

def create_archive(sub_dir, archive_name, history):
    tarPack = tarfile.open(archive_name, "w:gz")
    tarPack.add(sub_dir)
    tarPack.close()
    history[sub_dir] = int(time.time())

def save_history(dirs):
    archive_doc = xml.dom.minidom.Document()
    archive_tag = archive_doc.createElement("archive")
    archive_tag.setAttribute("version", '1')
    archive_doc.appendChild(archive_tag)
    for sub_dir in dirs:
        dir_tag = create_dir_tag(sub_dir, dirs, archive_doc)
        archive_tag.appendChild(dir_tag)
    file_archive = open('archive-history.xml', 'w')
    file_archive.write(archive_doc.toprettyxml(indent="    ", encoding="UTF-8"))
    file_archive.close()
    
def create_dir_tag(sub_dir, dirs, archive_doc):
    dir_tag = archive_doc.createElement("directory")
    dir_tag.setAttribute("name", sub_dir)
    last_archivized = dirs[sub_dir]
    last_archivized_str = sec_to_str_time(last_archivized)
    dir_tag.setAttribute("lastArchivized", last_archivized_str)
    return dir_tag   

def sec_to_str_time(secnum=None):
    return time.strftime('%Y-%m-%d %H:%M:%S GMT', time.gmtime(secnum)) 
    
class ExcInvalidFormat(Exception):
    pass    

def main():
    history = parse_archive_history()
    history = update_archives('.', history)
    save_history(history)

if __name__ == '__main__':
    main()
