from django.contrib import admin
from .models import *

admin.site.register(Profile)
admin.site.register(Post)
admin.site.register(Like)
admin.site.register(Comment)
admin.site.register(Follow)
admin.site.register(Message)
admin.site.register(Notification)