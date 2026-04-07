from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.core.validators import FileExtensionValidator

class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    bio = models.TextField(max_length=500, blank=True)
    profile_pic = models.ImageField(
        upload_to='profile_pics/', 
        blank=True, 
        null=True,
        validators=[
            FileExtensionValidator(allowed_extensions=['jpg', 'jpeg', 'png', 'gif'])
        ]
    )
    
    def __str__(self):
        return self.user.username
    
    def save(self, *args, **kwargs):
        try:
            this = Profile.objects.get(id=self.id)
            if this.profile_pic and this.profile_pic != self.profile_pic:
                this.profile_pic.delete(save=False)
        except Profile.DoesNotExist:
            pass
        
        super().save(*args, **kwargs)
    
    def follower_count(self):
        return Follow.objects.filter(following=self.user).count()
    
    def following_count(self):
        return Follow.objects.filter(follower=self.user).count()

@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.create(user=instance)

@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    instance.profile.save()
    
class Post(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    share_count = models.PositiveIntegerField(default=0)
    
    def __str__(self):
        return f'{self.user.username}: {self.content[:50]}'
    
    def like_count(self):
        return Like.objects.filter(post=self).count()
    
    def comment_count(self):
        return Comment.objects.filter(post=self).count()
    
    # Add this method
    def is_edited(self):
        """Since we don't have updated_at, always return False"""
        return False
    
    

class Like(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    post = models.ForeignKey(Post, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ('user', 'post')

class Comment(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    post = models.ForeignKey(Post, on_delete=models.CASCADE)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f'{self.user.username}: {self.content[:50]}'
    
    class Meta:
        ordering = ['created_at']  # Add this line for proper ordering

class Follow(models.Model):
    follower = models.ForeignKey(User, related_name='following', on_delete=models.CASCADE)
    following = models.ForeignKey(User, related_name='followers', on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ('follower', 'following')
    
    def __str__(self):
        return f'{self.follower.username} follows {self.following.username}'

class Message(models.Model):
    sender = models.ForeignKey(User, related_name='sent_messages', on_delete=models.CASCADE)
    receiver = models.ForeignKey(User, related_name='received_messages', on_delete=models.CASCADE)
    content = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)
    
    def __str__(self):
        return f'{self.sender.username} to {self.receiver.username}'

class Notification(models.Model):
    NOTIFICATION_TYPES = (
        ('like', 'Like'),
        ('comment', 'Comment'),
        ('follow', 'Follow'),
        ('friend_request', 'Friend Request'),
        ('tag', 'Tagged in Post'),
        ('post', 'New Post'),
        ('message', 'Message'),
    )
    
    recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    actor = models.ForeignKey(User, on_delete=models.CASCADE, related_name='actor_notifications', null=True, blank=True) 
    type = models.CharField(max_length=20, choices=NOTIFICATION_TYPES, default='follow')  
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    
    # Generic foreign key fields
    target_post = models.ForeignKey('Post', on_delete=models.SET_NULL, null=True, blank=True)
    target_comment = models.ForeignKey('Comment', on_delete=models.SET_NULL, null=True, blank=True)
    target_user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='target_notifications')
    
    def get_redirect_url(self):
        """Get the URL to redirect to when notification is clicked"""
        if self.type == 'like' and self.target_post:
            return f'/post/{self.target_post.id}/'
        elif self.type == 'comment' and self.target_post:
            return f'/post/{self.target_post.id}/'
        elif self.type == 'follow' and self.actor:
            return f'/profile/{self.actor.username}/'
        elif self.type == 'friend_request' and self.actor:
            return f'/profile/{self.actor.username}/'
        elif self.type == 'tag' and self.target_post:
            return f'/post/{self.target_post.id}/'
        elif self.type == 'post' and self.target_post:
            return f'/post/{self.target_post.id}/'
        elif self.type == 'message' and self.actor:
            return f'/messages/?user={self.actor.username}'
        elif self.actor:
            return f'/profile/{self.actor.username}/'
        else:
            return '/'
    
    def __str__(self):
        actor_name = self.actor.username if self.actor else "Unknown"
        return f"{actor_name} -> {self.recipient.username}: {self.get_type_display()}"
    
