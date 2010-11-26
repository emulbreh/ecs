# -*- coding: utf-8 -*-

import hashlib
import os
import tempfile
import datetime
import mimetypes
from uuid import uuid4

from django.db import models
from django.db.models.signals import post_save, post_delete
from django.core.files.storage import FileSystemStorage
from django.core.files import File
from django.utils._os import safe_join
from django.utils.encoding import smart_str
from django.conf import settings
from django.core.exceptions import ValidationError
from django.template.defaultfilters import slugify
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.generic import GenericForeignKey
from django.contrib.auth.models import User

from ecs.utils.pdfutils import pdf_page_count, pdf_isvalid
from ecs.authorization import AuthorizationManager


class DocumentPersonalization(models.Model):
    id = models.SlugField(max_length=36, primary_key=True, default=lambda: uuid4().get_hex())
    document = models.ForeignKey('Document', db_index=True)
    user = models.ForeignKey(User, db_index=True)
    
    def __unicode__(self):
        return "%s - %s - %s - %s" % (self.id, str(self.document), self.document.get_filename(), self.user.get_full_name())


class DocumentType(models.Model):
    name = models.CharField(max_length=100)
    identifier = models.CharField(max_length=30, db_index=True, blank=True, default= "")
    helptext = models.TextField(blank=True, default="")

    def __unicode__(self):
        return self.name

def incoming_document_to(instance=None, filename=None):
    instance.original_file_name = os.path.basename(os.path.normpath(filename)) # save original_file_name
    _, file_ext = os.path.splitext(filename)
    target_name = os.path.normpath(os.path.join(settings.INCOMING_FILESTORE, instance.uuid_document + file_ext[:5]))
    return target_name
    
class DocumentFileStorage(FileSystemStorage):
    def get_available_name(self, name):
        """
        Returns a filename that's free on the target storage system, and
        available for new content to be written to.
        Limit the length to some reasonable value.
        """
        dir_name, file_name = os.path.split(name)
        file_root, file_ext = os.path.splitext(file_name)
        # If the filename already exists, add _ with a 4 digit number till we get an empty slot.
        counter = 0
        while self.exists(name):
            # file_ext includes the dot.
            counter += 1
            name = os.path.join(dir_name, "%s_%04d%s" % (file_root, counter, file_ext))
        print name
        return name

    def path(self, name):
        # We need to overwrite the default behavior, because django won't let us save documents outside of MEDIA_ROOT
        return smart_str(os.path.normpath(name))


class DocumentManager(AuthorizationManager): 
    def create_from_buffer(self, buf, **kwargs): 
        tmp = tempfile.NamedTemporaryFile() 
        tmp.write(buf) 
        tmp.flush() 
        tmp.seek(0) 
        kwargs.setdefault('date', datetime.datetime.now()) 
        doc = self.create(file=File(tmp), **kwargs) 
        tmp.close() 
        return doc


C_BRANDING_CHOICES = (
    ('b', 'brand id'),
    ('p', 'personalize'),
    ('n', 'never brand'),
    )

class Document(models.Model):
    uuid_document = models.SlugField(max_length=36, unique=True)
    hash = models.SlugField(max_length=32)
    file = models.FileField(null=True, upload_to=incoming_document_to, storage=DocumentFileStorage(), max_length=250)
    original_file_name = models.CharField(max_length=250, null=True, blank=True)
    doctype = models.ForeignKey(DocumentType, null=True, blank=True)
    mimetype = models.CharField(max_length=100, default='application/pdf')
    pages = models.IntegerField(null=True, blank=True)
    branding = models.CharField(max_length=1, default='b', choices=C_BRANDING_CHOICES)
    allow_download = models.BooleanField(default=True)

    version = models.CharField(max_length=250)
    date = models.DateTimeField()
    deleted = models.BooleanField(default=False, blank=True)
    
    content_type = models.ForeignKey(ContentType, null=True)
    object_id = models.PositiveIntegerField(null=True)
    parent_object = GenericForeignKey('content_type', 'object_id')
    replaces_document = models.ForeignKey('Document', null=True, blank=True)
    
    objects = DocumentManager()
    
    def __unicode__(self):
        t = "Sonstige Unterlagen"
        if self.doctype_id:
            t = self.doctype.name
        return "%s Version %s vom %s" % (t, self.version, self.date.strftime('%d.%m.%Y'))

    def get_filename(self):
        ext = mimetypes.guess_extension(self.mimetype)
        name_slices = [self.doctype and self.doctype.name or 'Unterlage', self.version, self.date.strftime('%Y.%m.%d')]
        if self.parent_object and hasattr(self.parent_object, 'get_filename_slice'):
            name_slices.insert(0, self.parent_object.get_filename_slice())
        name = slugify('-'.join(name_slices))
        fullname = '%s%s' % (name, ext)
        return fullname

    def get_personalizations(self, user=None):
        ''' Get a list of (id, user) tuples of personalizations for this document, or None if none exist '''
        return None
        
    def add_personalization(self, user):
        ''' Add unique id connected to a user and document download ''' 
        return "unique id"

    def save(self, **kwargs):
        from ecs.documents.tasks import encrypt_and_upload_to_storagevault
              
        if not self.file:
            raise ValueError('no file')

        if not self.uuid_document: 
            self.uuid_document = uuid4().get_hex() # generate a new random uuid
            content_type, encoding = mimetypes.guess_type(self.file.name) # look what kind of mimetype we would guess

            if self.mimetype == 'application/pdf' or content_type == 'application/pdf':
                if not pdf_isvalid(self.file):
                    raise ValidationError('no valid pdf')

        if not self.hash:
            m = hashlib.md5() # calculate hash sum
            self.file.seek(0)
            while True:
                data= self.file.read(8192)
                if not data: break
                m.update(data)
            self.file.seek(0)
            self.hash = m.hexdigest()
                       
        if self.mimetype == 'application/pdf':
            self.pages = pdf_page_count(self.file) # calculate number of pages

        first_save = True if self.pk is None else False
        super(Document, self).save(**kwargs)
        
        if first_save:
            #print("doc file %s , path %s, original %s" % (str(self.file.name), str(self.file.path), str(self.original_file_name)))
            # upload it via celery to the storage vault
            encrypt_and_upload_to_storagevault.apply_async(args=[self.pk], countdown=3)

class Page(models.Model):
    doc = models.ForeignKey(Document)
    num = models.PositiveIntegerField()
    text = models.TextField()        
        
def _post_page_delete(sender, **kwargs):
    from haystack import site
    site.get_index(Page).remove_object(kwargs['instance'])

post_delete.connect(_post_page_delete, sender=Page)

