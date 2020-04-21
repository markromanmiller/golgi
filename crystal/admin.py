from django.contrib import admin

# Register your models here.

from .models import Publication, Network, Profile, PublicationTag

admin.site.register(Publication)
admin.site.register(Network)
admin.site.register(Profile)
admin.site.register(PublicationTag)