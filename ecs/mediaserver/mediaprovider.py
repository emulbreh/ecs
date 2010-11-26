# -*- coding: utf-8 -*-

import os, getpass, tempfile

from django.conf import settings

from ecs.utils.pathutils import tempfilecopy
from ecs.utils.storagevault import getVault
from ecs.utils.diskbuckets import DiskBuckets  
from ecs.utils.gpgutils import decrypt_verify
from ecs.mediaserver.tasks import rerender_pages
 
 
class MediaProvider(object):
    '''
    a central document storage and retrieval facility.
    Implements caching layers, rules, storage logic
    
    @attention: getBlob, getPage may raise KeyError in case getting of data went wrong
    '''

    def __init__(self):
        self.render_memcache = VolatileCache()
        self.render_diskcache = DiskCache(os.path.join(settings.MS_SERVER ["render_diskcache"], "pages"),
            settings.MS_SERVER ["render_diskcache_maxsize"])
        self.doc_diskcache = DiskCache(os.path.join(settings.MS_SERVER ["doc_diskcache"], "blobs"),
            settings.MS_SERVER ["doc_diskcache_maxsize"])
        self.vault = getVault()


    def _addBlob(self, identifier, filelike): 
        ''' this is a test function and should not be used normal '''
        self.vault.add(identifier, filelike)

        
    def getBlob(self, identifier, try_diskcache=True, try_vault=True):
        '''get a blob (unidentified media data)
        @raise KeyError: if reading the data of the identifier went wrong 
        '''
        filelike=None
        
        if try_diskcache:
            filelike = self.doc_diskcache.get(identifier)
        
        if not filelike and try_vault and identifier:
            try:
                filelike = self.vault.get(identifier)
            except KeyError as exceptobj:
                raise 
            
            if hasattr(filelike, "name"):
                inputfilename = filelike.name
            else:
                inputfilename = tempfilecopy(filelike) 
            
            try:
                osdescriptor, decryptedfilename = tempfile.mkstemp(); os.close(osdescriptor)
                decrypt_verify(inputfilename, decryptedfilename, settings.STORAGE_DECRYPT["gpghome"],
                    settings.STORAGE_DECRYPT ["owner"])
            except IOError as exceptobj:
                raise KeyError, "could not decrypt blob with identifier %s, exception was %r" % (identifier, exceptobj)
    
            try:
                with open(decryptedfilename, "rb") as decryptedfilelike:
                    self.doc_diskcache.create_or_update(identifier, decryptedfilelike)
            except IOError as exceptobj:
                raise KeyError, "could not put decrypted blob with identifier %s into diskcache, exception was %r" %(identifier, exceptobj)

            filelike = self.doc_diskcache.get(identifier)
        return filelike


    def setPage(self, page, filelike, use_render_memcache=False, use_render_diskcache=False):
        ''' set (create or update) a picture of an page of an document
        @param page: ecs.utils.pdfutils.Page Object
        '''
        identifier = str(page)
        if use_render_memcache:
            self.render_memcache.set(identifier, filelike)
        if use_render_diskcache:
            self.render_diskcache.create_or_update(identifier, filelike)


    def getPage(self, page, try_memcache=True, try_diskcache=True):
        ''' get a picture of an page of an document  
        @param page: ecs.utils.pdfutils.Page Object 
        @raise KeyError: if page could not loaded 
        '''
        filelike = None
        identifier = str(page)
        
        if try_memcache:     
            filelike = self.render_memcache.get(identifier)
        
        if filelike:
            self.render_diskcache.touch_accesstime(identifier) # update access in page cache
        else:
            if try_diskcache:
                filelike = self.render_diskcache.get(identifier) 
                if filelike:
                    self.doc_diskcache.touch_accesstime(page.id) # but update access in document diskcache
                else: 
                    # still not here, so we need to recache from scratch
                    result = rerender_pages.apply_async(args=[page.id,])
                    # we wait for an answer, meaning rendering is async, but view waits
                    success, used_identifier, additional_msg = result.get()
                    if not success: 
                        raise KeyError, "could not load page for document %s, error was %s" % (identifier, additional_msg)
                    else:
                        filelike = self.render_diskcache.get(identifier)
                        
                self.render_memcache.set(identifier, filelike)
                filelike.seek(0)
        return filelike

 

class VolatileCache(object):
    '''
    A volatile, key/value, self aging, fixedsize cache using memcache
    '''

    def __init__(self):
        if settings.MS_SERVER ["render_memcache_lib"] == 'memcache':
            import memcache as memcache
        elif settings.MS_SERVER ["render_memcache_lib"] == 'mockcache' or settings.MS_SERVER ["render_memcache_lib"] == '' :
            import mockcache as memcache
        else:
            raise NotImplementedError('i do not know about %s as render_memcache_lib' % settings.MS_SERVER ["render_memcache_lib"])

        self.ns = '%s.ms' % getpass.getuser()
        self.mc = memcache.Client(['%s:%d' % (settings.MS_SERVER ["render_memcache_host"],
            settings.MS_SERVER ["render_memcache_port"])], debug=False)

    def set(self, identifier, filelike):
        ''' set (create_or_update) data value of identifier) '''
        if hasattr(filelike,"read"):
            self.mc.set("".join((identifier, self.ns)), filelike.read())
        else:
            self.mc.set("".join((identifier, self.ns)), filelike)
        
    def get(self, identifier):
        ''' get data value of identifier '''
        return self.mc.get("".join((identifier, self.ns)))

    def entries(self):
        ''' dump all values ''' 
        return self.mc.dictionary.values() 



class DiskCache(DiskBuckets):
    '''
    Persistent cache using directory buckets which are derived from the cache identifier of storage unit
    '''
    def __init__(self, root_dir, maxsize):
        self.maxsize = maxsize
        super(DiskCache, self).__init__(root_dir, allow_mkrootdir=True)

    def add(self, identifier, filelike):
        super(DiskCache, self).add(identifier, filelike)
    
    def create_or_update(self, identifier, filelike):
        super(DiskCache, self).create_or_update(identifier, filelike)
             
    def touch_accesstime(self, identifier):
        os.utime(self._generate_path(identifier), None)

    def get(self, identifier):
        if self.exists(identifier):
            self.touch_accesstime(identifier)
            return super(DiskCache, self).get(identifier)
        else:
            return None
        
    def age(self):
        entriesByAge = self.entries_by_age()
        cachesize = self.size()
        
        while cachesize < self.maxsize:
            oldest = entriesByAge.next()
            size = os.path.getsize(oldest)
            os.remove(oldest)
            cachesize -= size

    def entries_by_age(self):
        return list(reversed(sorted(self.entries(), key=os.path.getatime)))

    def entries(self):
        return [open(path,"rb") for path in os.walk(self.root_dir)]

    def size(self):
        return sum(os.path.getsize(entry) for entry in os.walk(self.root_dir))


