from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib import messages
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.http import JsonResponse
from django.db.models import Q, Count
from django.core.paginator import Paginator
from django.core.files.base import ContentFile
from .models import *
from .utils import generate_temp_password, send_temp_password_email
import json
import os
from PIL import Image
from io import BytesIO
from django.core.files.base import ContentFile
import base64
import uuid

def forget_password_view(request):
    if request.method == 'POST':
        email = request.POST.get('email')
        try:
            user = User.objects.get(email=email)
            temp_password = generate_temp_password()
            user.set_password(temp_password)
            user.save()
            email_sent = send_temp_password_email(email, temp_password)
            
            if email_sent:
                messages.success(request, 'A temporary password has been sent to your email. Please check your inbox.')
                return redirect('login')
            else:
                messages.error(request, 'Failed to send email. Please try again later.')
                
        except User.DoesNotExist:
            messages.success(request, 'If an account exists with this email, a temporary password has been sent.')
            return redirect('login')
            
        except Exception as e:
            messages.error(request, f'An error occurred: {str(e)}')
    
    return render(request, 'forgetpassword.html')

def compress_image(image):
    """Compress image to reduce file size"""
    try:
        img = Image.open(image)
        if img.mode in ('RGBA', 'LA', 'P'):
            background = Image.new('RGB', img.size, (255, 255, 255))
            if img.mode == 'P':
                img = img.convert('RGBA')
            background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
            img = background

        output = BytesIO()
        img.save(output, format='JPEG', quality=85, optimize=True)
        output.seek(0)
        
        return ContentFile(output.read(), name=image.name)
    except Exception as e:
        print(f"Error compressing image: {e}")
        return image
    
def visitor_home(request):
    """Show visitor homepage for non-logged in users"""
    # Show recent public posts
    public_posts = Post.objects.all().order_by('-created_at')[:10]
    
    # Get total user count for stats
    total_users = User.objects.count()
    total_posts = Post.objects.count()
    
    # Get some sample users for display
    sample_users = User.objects.order_by('-date_joined')[:6]
    
    return render(request, 'visitor_home.html', {
        'public_posts': public_posts,
        'total_users': total_users,
        'total_posts': total_posts,
        'sample_users': sample_users
    })

@csrf_exempt
@require_POST
@login_required
def follow_user(request):
    try:
        data = json.loads(request.body)
        user_id = data.get('user_id')
        
        if not user_id:
            return JsonResponse({'success': False, 'error': 'User ID is required'})
        
        user_to_follow = User.objects.get(id=user_id)
    
        if Follow.objects.filter(follower=request.user, following=user_to_follow).exists():
            return JsonResponse({'success': False, 'error': 'Already following this user'})
        
        # Create follow relationship
        Follow.objects.create(follower=request.user, following=user_to_follow)
        
        return JsonResponse({'success': True})
    except User.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'User not found'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})
    


@csrf_exempt
@login_required
def clear_all_notifications(request):
    """
    Clear all notifications for the current user
    """
    if request.method == 'POST':
        try:
            deleted_count, _ = Notification.objects.filter(
                recipient=request.user
            ).delete()
            
            return JsonResponse({
                'success': True,
                'message': f'Cleared {deleted_count} notifications',
                'deleted_count': deleted_count
            })
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': str(e)
            })
    
    return JsonResponse({'success': False, 'message': 'Invalid request method'})

@csrf_exempt
@login_required
def unfollow_user(request, username=None):
    """
    Combined function that handles both:
    1. AJAX unfollow requests (POST with user_id in JSON body)
    2. Regular unfollow requests (with username in URL)
    """

    if request.method == 'POST' and request.content_type == 'application/json':

        try:
            data = json.loads(request.body)
            user_id = data.get('user_id')
            
            if not user_id:
                return JsonResponse({'success': False, 'error': 'User ID is required'})
            
            user_to_unfollow = User.objects.get(id=user_id)
            

            deleted_count, _ = Follow.objects.filter(
                follower=request.user, 
                following=user_to_unfollow
            ).delete()
            
            if deleted_count > 0:
                return JsonResponse({'success': True})
            else:
                return JsonResponse({'success': False, 'error': 'Not following this user'})
                
        except User.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'User not found'})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    
    else:

        if not username:
            return JsonResponse({'success': False, 'error': 'Username is required'})
        
        user_to_unfollow = get_object_or_404(User, username=username)
        
        if request.user.id != user_to_unfollow.id:
            deleted_count, _ = Follow.objects.filter(
                follower_id=request.user.id,
                following=user_to_unfollow
            ).delete()
            
            if deleted_count > 0:
                # Get updated follower count
                follower_count = Follow.objects.filter(following=user_to_unfollow).count()
                return JsonResponse({
                    'success': True, 
                    'follower_count': follower_count
                })
        
        return JsonResponse({'success': False})


@login_required
def friend_suggestions(request):
    # Get current user
    current_user = request.user
    

    following_ids = Follow.objects.filter(
        follower=current_user
    ).values_list('following_id', flat=True)
    
    # Exclude self and already followed users
    suggestions = User.objects.exclude(
        id__in=following_ids
    ).exclude(
        id=current_user.id
    )
    
    
    suggestions = suggestions.annotate(
        followers_count=Count('followers'),
        following_count=Count('following')
    ).order_by('-followers_count')[:50]  
    
  
    for user in suggestions:
    
        current_following = set(following_ids)
        user_followers = set(Follow.objects.filter(
            following=user
        ).values_list('follower_id', flat=True))
        
        mutual_friends = current_following.intersection(user_followers)
        user.mutual_friends_count = len(mutual_friends)
        
      
        try:
            profile = Profile.objects.get(user=user)
            user.profile_picture = profile.profile_pic  
        except Profile.DoesNotExist:
            user.profile_picture = None
    

    suggestions = sorted(suggestions, key=lambda x: x.mutual_friends_count, reverse=True)
    
    paginator = Paginator(suggestions, 10)  
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'suggestions': page_obj,
        'following_ids': list(following_ids),
    }
    
    return render(request, 'friend_suggestions.html', context)
    
@login_required
def api_followers(request, username):
    """API endpoint to get REAL followers list"""
    user = get_object_or_404(User, username=username)
    
    follower_relations = Follow.objects.filter(following=user).select_related('follower')
    
    followers_data = []
    for relation in follower_relations:
        follower = relation.follower

        profile_pic_url = None
        try:
            if follower.profile.profile_pic:
                profile_pic_url = follower.profile.profile_pic.url
        except:
            pass
        
        followers_data.append({
            'username': follower.username,
            'full_name': follower.get_full_name() or follower.username,
            'profile_pic': profile_pic_url
        })
    
    return JsonResponse({
        'followers': followers_data,
        'count': len(followers_data)
    })

@login_required
def api_following(request, username):
    """API endpoint to get REAL following list"""
    user = get_object_or_404(User, username=username)
    

    following_relations = Follow.objects.filter(follower=user).select_related('following')
    
    following_data = []
    for relation in following_relations:
        following_user = relation.following

        profile_pic_url = None
        try:
            if following_user.profile.profile_pic:
                profile_pic_url = following_user.profile.profile_pic.url
        except:
            pass
        
        following_data.append({
            'username': following_user.username,
            'full_name': following_user.get_full_name() or following_user.username,
            'profile_pic': profile_pic_url
        })
    
    return JsonResponse({
        'following': following_data,
        'count': len(following_data)
    })

def register_view(request):
    if request.method == 'POST':
  
        first_name = request.POST['first_name'].strip()
        last_name = request.POST['last_name'].strip()
        username = request.POST['username'].strip()
        email = request.POST['email'].strip()
        password = request.POST['password']
        confirm_password = request.POST['confirm_password']
     
        if not first_name or not last_name:
            messages.error(request, "First name and last name are required!")
            return redirect('register')
        

        if password != confirm_password:
            messages.error(request, "Passwords don't match!")
            return redirect('register')
        
        if len(password) < 6:
            messages.error(request, "Password must be at least 6 characters!")
            return redirect('register')
 
        if User.objects.filter(username=username).exists():
            messages.error(request, "Username already exists!")
            return redirect('register')

        if User.objects.filter(email=email).exists():
            messages.error(request, "Email already registered!")
            return redirect('register')
        
        try:
         
            from .utils import generate_otp, send_otp_email

            # Generate OTP
            otp = generate_otp()

            # Store user data in session
            request.session['register_data'] = {
                'first_name': first_name,
                'last_name': last_name,
                'username': username,
                'email': email,
                'password': password,
            }

            request.session['otp'] = otp

            # Send OTP email
            if send_otp_email(email, otp):
                return redirect('verify_otp')
            else:
                messages.error(request, "Failed to send OTP")
                return redirect('register')
            
        except Exception as e:
            messages.error(request, f"An error occurred: {str(e)}")
            return redirect('register')
    
    return render(request, 'register.html')

def check_username(request):
    username = request.GET.get('username', '').strip()
    
    if not username:
        return JsonResponse({'available': False})
    

    exists = User.objects.filter(username__iexact=username).exists()
    
  
    is_valid = len(username) >= 3 and re.match(r'^[a-zA-Z0-9_]+$', username)
    
    return JsonResponse({
        'available': not exists and is_valid,
        'suggestions': get_username_suggestions(username) if exists else []
    })

def get_username_suggestions(username):
    """Generate username suggestions"""
    suggestions = []
    base = re.sub(r'[^a-zA-Z0-9_]', '', username)
    
    if len(base) < 3:
        return suggestions
    

    for i in range(1, 10):
        suggestion = f"{base}{i}"
        if not User.objects.filter(username__iexact=suggestion).exists():
            suggestions.append(suggestion)
        if len(suggestions) >= 3:
            break

    suggestion = f"{base}_"
    if not User.objects.filter(username__iexact=suggestion).exists():
        suggestions.append(suggestion)
    
    return suggestions[:3]


def login_view(request):
    if request.method == 'POST':
        username_or_email = request.POST.get('username_or_email', '').strip()
        password = request.POST.get('password', '')
        
        print(f"DEBUG: Login attempt with: {username_or_email}")
      
        if '@' in username_or_email and '.' in username_or_email:

            try:
                user = User.objects.get(email=username_or_email)
                username = user.username
                print(f"DEBUG: Found user by email: {username}")
            except User.DoesNotExist:
                print(f"DEBUG: No user found with email: {username_or_email}")
                messages.error(request, "Invalid email or password!")
                return redirect('login')
        else:
            # Treat as username
            username = username_or_email
            print(f"DEBUG: Treating as username: {username}")
        
        user = authenticate(request, username=username, password=password)
        
        if user is not None:
            login(request, user)

            remember_me = request.POST.get('remember_me')
            if not remember_me:
  
                request.session.set_expiry(0)
            
            messages.success(request, f"Welcome back, {user.first_name or user.username}!")
            return redirect('home')
        else:
            messages.error(request, "Invalid username/email or password!")
    
    return render(request, 'login.html')

@login_required
def edit_post(request, post_id):
    if request.method == 'POST':
        post = get_object_or_404(Post, id=post_id)

        if post.user != request.user:
            return JsonResponse({
                'success': False, 
                'error': 'You can only edit your own posts'
            })
        
        content = request.POST.get('content', '').strip()
        
        if not content:
            return JsonResponse({
                'success': False, 
                'error': 'Post content cannot be empty'
            })
        
        if len(content) > 1000:
            return JsonResponse({
                'success': False, 
                'error': 'Post content cannot exceed 1000 characters'
            })

        post.content = content
        post.save()

        from django.utils.html import linebreaks
        formatted_content = linebreaks(content)
        
        return JsonResponse({
            'success': True,
            'content': formatted_content,
            'message': 'Post updated successfully'
        })
    
    return JsonResponse({'success': False, 'error': 'Invalid request'})
    

@login_required
def logout_view(request):
    logout(request)
    return redirect('login')

# Home View (News Feed)
def home_view(request):
    """
    Home page - shows visitor landing page for non-logged in users
    Shows news feed for logged in users
    """
    
    if not request.user.is_authenticated:
      
        public_posts = Post.objects.all().order_by('-created_at')[:10]
        
        # Get total user count for stats
        total_users = User.objects.count()
        total_posts = Post.objects.count()
    
        sample_users = User.objects.order_by('-date_joined')[:6]
        
        return render(request, 'visitor_home.html', {
            'public_posts': public_posts,
            'total_users': total_users,
            'total_posts': total_posts,
            'sample_users': sample_users
        })
   
    following_ids = Follow.objects.filter(follower_id=request.user.id).values_list('following_id', flat=True)
  
    posts = Post.objects.filter(
        Q(user_id=request.user.id) | Q(user_id__in=following_ids)
    ).order_by('-created_at')
    
    followed_user_ids = Follow.objects.filter(follower_id=request.user.id).values_list('following_id', flat=True)
    suggestions = User.objects.exclude(
        Q(id=request.user.id) | 
        Q(id__in=followed_user_ids)
    ).order_by('?')[:5]  
    
    follower_count = Follow.objects.filter(following=request.user).count()
    following_count = Follow.objects.filter(follower=request.user).count()
    
    return render(request, 'home.html', {
        'posts': posts,
        'suggestions': suggestions,
        'follower_count': follower_count,
        'following_count': following_count
    })

def share_post(request, post_id):
    if request.method == 'POST':
        post = get_object_or_404(Post, id=post_id)
        post.share_count += 1
        post.save()
        return JsonResponse({'success': True, 'share_count': post.share_count})

@login_required
def create_post(request):
    if request.method == 'POST':
        content = request.POST.get('content', '').strip()
        if content:
            try:
                post = Post.objects.create(user=request.user, content=content)
                return JsonResponse({'success': True, 'post_id': post.id})
            except Exception as e:
                return JsonResponse({'success': False, 'error': str(e)})
        else:
            return JsonResponse({'success': False, 'error': 'Content cannot be empty'})
    return JsonResponse({'success': False, 'error': 'Invalid request method'})

@login_required
def profile_view(request, username):
    user = get_object_or_404(User, username=username)
    posts = Post.objects.filter(user=user).order_by('-created_at')
 
    for post in posts:
        post.comment_count_value = Comment.objects.filter(post=post).count()
    
    is_following = Follow.objects.filter(follower=request.user, following=user).exists()
    

    follower_count = Follow.objects.filter(following=user).count()
    following_count = Follow.objects.filter(follower=user).count()
    
    return render(request, 'profile.html', {
        'profile_user': user,
        'posts': posts,
        'is_following': is_following,
        'follower_count': follower_count,
        'following_count': following_count
    })

@login_required
def edit_profile(request):
    if request.method == 'POST':
        # Handle remove profile picture request
        if 'remove_profile_pic' in request.POST:
            try:
                if request.user.profile.profile_pic:
                    # Delete the file from storage
                    request.user.profile.profile_pic.delete(save=False)
                    request.user.profile.profile_pic = None
                    request.user.profile.save()
                    messages.success(request, "Profile picture removed successfully!")
                else:
                    messages.info(request, "No profile picture to remove.")
            except Exception as e:
                messages.error(request, f"Error removing profile picture: {str(e)}")
            
            return redirect('edit_profile')
        
        # Handle regular profile update
        profile = request.user.profile
        profile.bio = request.POST.get('bio', '')
        
        if 'first_name' in request.POST:
            new_first_name = request.POST['first_name'].strip()
            if new_first_name and new_first_name != request.user.first_name:
                request.user.first_name = new_first_name
                request.user.save()
        
        if 'last_name' in request.POST:
            new_last_name = request.POST['last_name'].strip()
            if new_last_name and new_last_name != request.user.last_name:
                request.user.last_name = new_last_name
                request.user.save()

        if 'profile_pic' in request.FILES:
            uploaded_file = request.FILES['profile_pic']
            
            if uploaded_file.size > 2 * 1024 * 1024:
                messages.error(request, "Image file too large ( > 2MB )")
                return redirect('edit_profile')
    
            valid_extensions = ['jpg', 'jpeg', 'png', 'gif']
            extension = uploaded_file.name.split('.')[-1].lower()
            if extension not in valid_extensions:
                messages.error(request, "Unsupported file format. Please upload JPG, PNG, or GIF.")
                return redirect('edit_profile')

            try:          
                if 'cropped_image' in request.POST and request.POST['cropped_image']:
                    # Handle cropped image from JavaScript
                    import base64
                    import uuid
                    
                    cropped_data = request.POST['cropped_image']
                    if cropped_data and cropped_data.startswith('data:image'):
                        format, imgstr = cropped_data.split(';base64,')
                        ext = format.split('/')[-1]
                        
                        # Delete old picture if exists
                        if request.user.profile.profile_pic:
                            request.user.profile.profile_pic.delete(save=False)
                        
                        # Save new picture
                        filename = f"profile_pics/{uuid.uuid4()}.{ext}"
                        request.user.profile.profile_pic.save(filename, ContentFile(base64.b64decode(imgstr)), save=False)
                else:
                    compressed_file = compress_image(uploaded_file)
                    import uuid
                    filename = f"profile_pics/{uuid.uuid4()}.jpg"
                    profile.profile_pic.save(filename, compressed_file, save=False)
                    
            except Exception as e:
                print(f"Error processing image: {e}")
                profile.profile_pic = uploaded_file
        
        profile.save()
        
        # Handle username update
        if 'username' in request.POST:
            new_username = request.POST['username']
            if new_username != request.user.username:
                if not User.objects.filter(username=new_username).exists():
                    request.user.username = new_username
                    request.user.save()
                else:
                    messages.error(request, "Username already exists!")
        
        messages.success(request, "Profile updated successfully!")
        return redirect('profile', username=request.user.username)
    
    return render(request, 'edit_profile.html')

from django.db.models import Q

@login_required
def search_users(request):
    query = request.GET.get('q', '').strip()
    
    if query:
      
        users = User.objects.filter(
            Q(username__icontains=query) |
            Q(first_name__icontains=query) |
            Q(last_name__icontains=query)
        ).exclude(id=request.user.id).order_by('-date_joined')[:50]
        
        query_parts = query.split()
        if len(query_parts) >= 2 and not users.exists():

            users = User.objects.filter(
                Q(first_name__icontains=query_parts[0]) & 
                Q(last_name__icontains=' '.join(query_parts[1:])) |
                Q(username__icontains=query)
            ).exclude(id=request.user.id).order_by('-date_joined')[:50]
        

        users_with_status = []
        for user in users:
            is_following = Follow.objects.filter(
                follower_id=request.user.id, 
                following=user
            ).exists()
            
            users_with_status.append({
                'user': user,
                'is_following': is_following
            })
        
        popular_users = User.objects.annotate(
            follower_count=Count('followers')
        ).order_by('-follower_count', '-date_joined')[:10]
        
        recent_users = User.objects.order_by('-last_login')[:20]
        
    else:
        users_with_status = []
        popular_users = User.objects.annotate(
            follower_count=Count('followers')
        ).order_by('-follower_count', '-date_joined')[:10]
        recent_users = User.objects.order_by('-last_login')[:20]
    
    return render(request, 'search.html', {
        'users': users_with_status, 
        'query': query,
        'popular_users': popular_users,
        'recent_users': recent_users
    })


@login_required
def send_message(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        receiver_username = data.get('receiver')
        content = data.get('content')
        
        receiver = get_object_or_404(User, username=receiver_username)
        
        Message.objects.create(
            sender=request.user,
            receiver=receiver,
            content=content
        )
        
        return JsonResponse({'success': True})
    
    return JsonResponse({'success': False})


@login_required
def get_messages(request, username):
    other_user = get_object_or_404(User, username=username)
    
    messages = Message.objects.filter(
        (Q(sender=request.user) & Q(receiver=other_user)) |
        (Q(sender=other_user) & Q(receiver=request.user))
    ).order_by('timestamp')
    
 
    Message.objects.filter(sender=other_user, receiver=request.user, is_read=False).update(is_read=True)
    
    messages_data = []
    for msg in messages:
        messages_data.append({
            'id': msg.id,
            'sender': msg.sender.username,
            'content': msg.content,
            'timestamp': msg.timestamp.strftime('%H:%M'),
            'is_me': msg.sender == request.user
        })
    
    return JsonResponse({'messages': messages_data})

@login_required
def like_post(request, post_id):
    post = get_object_or_404(Post, id=post_id)
    
    like, created = Like.objects.get_or_create(user=request.user, post=post)
    
    if not created:
        like.delete()
        return JsonResponse({'liked': False, 'count': post.like_count()})
    else:
    
        if request.user != post.user:
            Notification.objects.create(
                recipient=post.user,
                actor=request.user,
                type='like',
                target_post=post
            )
    
    return JsonResponse({'liked': True, 'count': post.like_count()})

@login_required
def add_comment(request, post_id):
    if request.method == 'POST':
        post = get_object_or_404(Post, id=post_id)
        content = request.POST.get('content', '').strip()
        
        if content:
            comment = Comment.objects.create(
                user=request.user,
                post=post,
                content=content
            )

            if post.user != request.user:
                Notification.objects.create(
                    recipient=post.user,
                    actor=request.user,
                    type='comment',
                    target_post=post,
                    target_comment=comment
                )
            
            return JsonResponse({
                'success': True,
                'comment': {
                    'id': comment.id,
                    'user': comment.user.username,
                    'content': comment.content,
                    'created_at': comment.created_at.strftime('%H:%M')
                }
            })
    
    return JsonResponse({'success': False})

@login_required
def get_comments(request, post_id):
    post = get_object_or_404(Post, id=post_id)
    comments = Comment.objects.filter(post=post).order_by('created_at')
    
    comments_data = []
    for comment in comments:

        if comment.user.profile.profile_pic:
            profile_pic_url = comment.user.profile.profile_pic.url
        else:
            profile_pic_url = '/static/default_profile.png'  
        
        comments_data.append({
            'id': comment.id,
            'user': comment.user.username,
            'content': comment.content,
            'created_at': comment.created_at.strftime('%H:%M'),
            'profile_pic': profile_pic_url
        })
    
    return JsonResponse({'comments': comments_data})

@login_required
def change_password(request):
    if request.method == 'POST':
        old_password = request.POST['old_password']
        new_password = request.POST['new_password']
        confirm_password = request.POST['confirm_password']
        
        if not request.user.check_password(old_password):
            messages.error(request, "Old password is incorrect!")
            return redirect('edit_profile')
        
        if new_password != confirm_password:
            messages.error(request, "New passwords don't match!")
            return redirect('edit_profile')
        
        request.user.set_password(new_password)
        request.user.save()
        
        # Re-login user
        login(request, request.user)
        messages.success(request, "Password changed successfully!")
        return redirect('profile', username=request.user.username)
    
    return redirect('edit_profile')

@login_required
def delete_post(request, post_id):
    post = get_object_or_404(Post, id=post_id)
    
    if post.user == request.user:
        post.delete()
        return JsonResponse({'success': True})
    
    return JsonResponse({'success': False})


from django.core.mail import send_mail
from django.utils.crypto import get_random_string

def forgot_password(request):
    if request.method == 'POST':
        email = request.POST['email']
        
        try:
            user = User.objects.get(email=email)

            temp_password = get_random_string(8)
            user.set_password(temp_password)
            user.save()
            
 
            send_mail(
                'Password Reset Request',
                f'Your temporary password is: {temp_password}\nPlease change it after login.',
                'noreply@socialapp.com',
                [email],
                fail_silently=False,
            )
            
            messages.success(request, 'Temporary password sent to your email!')
            return redirect('login')
            
        except User.DoesNotExist:
            messages.error(request, 'Email not found!')
    
    return render(request, 'forgot_password.html')


@login_required
def messages_view(request):

    sent_users = Message.objects.filter(sender=request.user).values_list('receiver', flat=True).distinct()
    received_users = Message.objects.filter(receiver=request.user).values_list('sender', flat=True).distinct()

    all_user_ids = set(list(sent_users) + list(received_users))
    conversations = []
    
    for user_id in all_user_ids:
        try:
            user = User.objects.get(id=user_id)
            
            last_message = Message.objects.filter(
                (Q(sender=request.user) & Q(receiver=user)) |
                (Q(sender=user) & Q(receiver=request.user))
            ).order_by('-timestamp').first()
            
            unread_count = Message.objects.filter(
                sender=user, receiver=request.user, is_read=False
            ).count()
            
            conversations.append({
                'user': user,
                'last_message': last_message.content if last_message else 'No messages yet',
                'last_time': last_message.timestamp if last_message else None,
                'unread_count': unread_count
            })
        except User.DoesNotExist:
            continue

    conversations.sort(key=lambda x: x['last_time'] if x['last_time'] else timezone.now(), reverse=True)
    
    return render(request, 'messages.html', {'conversations': conversations})

@login_required
def get_user_info(request, username):
    try:
        user = User.objects.get(username=username)
        
        profile_pic = None
        if user.profile.profile_pic:
            profile_pic = user.profile.profile_pic.url
        
        return JsonResponse({
            'success': True,
            'user_id': user.id,
            'username': user.username,
            'profile_pic': profile_pic or 'https://via.placeholder.com/100'
        })
    except User.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'User not found'})
    
@login_required
def notifications_view(request):
    notifications = Notification.objects.filter(recipient=request.user).order_by('-created_at')
    
    # Get which users the current user is following
    following_ids = Follow.objects.filter(
        follower=request.user
    ).values_list('following_id', flat=True)
    
    # Add follow status to each notification
    for notification in notifications:
        notification.is_current_user_following = False
        if notification.actor and notification.actor.id in following_ids:
            notification.is_current_user_following = True
    
    unread_count = notifications.filter(is_read=False).count()

    notif_type = request.GET.get('type')
    if notif_type == 'unread':
        notifications = notifications.filter(is_read=False)
    
    for notification in notifications:
        try:
            profile = Profile.objects.get(user=notification.actor)
            notification.actor_profile_pic = profile.profile_pic.url if profile.profile_pic else None
        except Profile.DoesNotExist:
            notification.actor_profile_pic = None
    
    from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
    page = request.GET.get('page', 1)
    paginator = Paginator(notifications, 20)
    
    try:
        notifications_page = paginator.page(page)
    except PageNotAnInteger:
        notifications_page = paginator.page(1)
    except EmptyPage:
        notifications_page = paginator.page(paginator.num_pages)
    
    return render(request, 'notifications.html', {
        'notifications': notifications_page,
        'unread_count': unread_count  
    })


@login_required
def get_conversations(request):
    conversations = []
    # Similar logic to messages_view but return JSON
    return JsonResponse({'conversations': conversations})

@login_required
def get_unread_counts(request):
    unread_messages = Message.objects.filter(receiver=request.user, is_read=False).count()
    unread_notifications = Notification.objects.filter(user=request.user, is_read=False).count()
    
    return JsonResponse({
        'unread_messages': unread_messages,
        'unread_notifications': unread_notifications
    })

@login_required
def mark_messages_read(request, username):
    other_user = get_object_or_404(User, username=username)
    Message.objects.filter(sender=other_user, receiver=request.user, is_read=False).update(is_read=True)
    return JsonResponse({'success': True})

@csrf_exempt
@login_required
def mark_notification_read(request, notification_id):
    """Mark a single notification as read"""
    try:
        notification = Notification.objects.get(id=notification_id, recipient=request.user)
        notification.is_read = True
        notification.save()
        return JsonResponse({'success': True})
    except Notification.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Notification not found'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

@csrf_exempt
@login_required
def mark_all_notifications_read(request):
    """Mark all notifications as read for current user"""
    if request.method == 'POST':
        try:
            updated_count = Notification.objects.filter(
                recipient=request.user, 
                is_read=False
            ).update(is_read=True)
            
            return JsonResponse({
                'success': True, 
                'updated_count': updated_count
            })
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    
    return JsonResponse({'success': False, 'error': 'Invalid request method'})


@csrf_exempt
@login_required
def follow_user(request, username=None):
    """
    Combined function that handles both:
    1. AJAX requests (POST with user_id in JSON body)
    2. Regular requests (GET/POST with username in URL)
    """
    
   
    if request.method == 'POST' and request.content_type == 'application/json':
      
        try:
            data = json.loads(request.body)
            user_id = data.get('user_id')
            
            if not user_id:
                return JsonResponse({'success': False, 'error': 'User ID is required'})
            
            user_to_follow = User.objects.get(id=user_id)
        
            if Follow.objects.filter(follower=request.user, following=user_to_follow).exists():
                return JsonResponse({'success': False, 'error': 'Already following this user'})
  
            Follow.objects.create(follower=request.user, following=user_to_follow)
            
            Notification.objects.create(
                recipient=user_to_follow,
                actor=request.user,
                type='follow'
            )
            
            return JsonResponse({'success': True})
            
        except User.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'User not found'})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    
    else:
        if not username:
            return JsonResponse({'followed': False, 'error': 'Username is required'})
        
        user_to_follow = get_object_or_404(User, username=username)
        
        if request.user.id != user_to_follow.id:
            follow, created = Follow.objects.get_or_create(
                follower_id=request.user.id,
                following=user_to_follow
            )
            
            if not created:
                follow.delete()

                follower_count = Follow.objects.filter(following=user_to_follow).count()
                return JsonResponse({
                    'followed': False, 
                    'follower_count': follower_count
                })

            Notification.objects.create(
                recipient=user_to_follow,
                actor=request.user,
                type='follow'
            )
            
            follower_count = Follow.objects.filter(following=user_to_follow).count()
            
            return JsonResponse({
                'followed': True, 
                'follower_count': follower_count
            })
        
        return JsonResponse({'followed': False})
    

@login_required
def check_new_messages(request, username):
    other_user = get_object_or_404(User, username=username)
    last_message_id = request.GET.get('last_id', 0)
    
    new_messages = Message.objects.filter(
        sender=other_user,
        receiver=request.user,
        id__gt=last_message_id,
        is_read=False
    ).order_by('timestamp')
    
    messages_data = []
    for msg in new_messages:
        messages_data.append({
            'id': msg.id,
            'sender': msg.sender.username,
            'content': msg.content,
            'timestamp': msg.timestamp.strftime('%H:%M'),
            'is_me': False
        })
    
    is_typing = False  
    
    return JsonResponse({
        'new_messages': messages_data,
        'is_typing': is_typing
    })

@login_required
def typing_indicator(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        receiver_username = data.get('receiver')
        is_typing = data.get('is_typing', False)
        
        receiver = get_object_or_404(User, username=receiver_username)

        from django.core.cache import cache
        cache_key = f'typing_{receiver.id}_{request.user.id}'
        cache.set(cache_key, is_typing, timeout=5)
        
        return JsonResponse({'success': True})
    
    return JsonResponse({'success': False})

@login_required
def get_typing_status(request, username):
    other_user = get_object_or_404(User, username=username)
    
    from django.core.cache import cache
    cache_key = f'typing_{request.user.id}_{other_user.id}'
    is_typing = cache.get(cache_key, False)
    
    return JsonResponse({'is_typing': is_typing})


@login_required
def accept_friend_request(request, username):
    """Accept friend request and create friendship"""
    user = get_object_or_404(User, username=username)

    Follow.objects.get_or_create(follower=request.user, following=user)
    Follow.objects.get_or_create(follower=user, following=request.user)
    
    Notification.objects.filter(
        recipient=request.user,
        actor=user,
        type='friend_request'
    ).delete()
    
    return JsonResponse({'success': True})

@login_required
def decline_friend_request(request, username):
    """Decline friend request"""
    user = get_object_or_404(User, username=username)
    
    Notification.objects.filter(
        recipient=request.user,
        actor=user,
        type='friend_request'
    ).delete()
    
    return JsonResponse({'success': True})

@login_required
def get_unread_counts(request):
    """Get unread message and notification counts"""
    unread_messages = Message.objects.filter(receiver=request.user, is_read=False).count()
    unread_notifications = Notification.objects.filter(recipient=request.user, is_read=False).count()
    
    return JsonResponse({
        'unread_messages': unread_messages,
        'unread_notifications': unread_notifications
    })

@login_required
def post_detail_view(request, post_id):
    """View for individual post page"""
    post = get_object_or_404(Post, id=post_id)
    comments = Comment.objects.filter(post=post).order_by('created_at')
    user_has_liked = Like.objects.filter(user=request.user, post=post).exists()
    return render(request, 'home.html', {
        'posts': [post], 
        'single_post_view': True,  
        'post': post,
        'comments': comments,
        'user_has_liked': user_has_liked
    })
def verify_otp(request):
    if request.method == 'POST':
        user_otp = request.POST.get('otp')
        session_otp = request.session.get('otp')

        if user_otp == session_otp:
            data = request.session.get('register_data')

            user = User.objects.create_user(
                username=data['username'],
                email=data['email'],
                password=data['password'],
                first_name=data['first_name'],
                last_name=data['last_name']
            )

            # Clear session
            request.session.pop('otp', None)
            request.session.pop('register_data', None)

            login(request, user)
            messages.success(request, "Account created successfully!")
            return redirect('home')
        else:
            messages.error(request, "Invalid OTP")

    return render(request, 'verify_otp.html')


from .utils import generate_otp, send_otp_email

def resend_otp(request):
    data = request.session.get('register_data')

    if not data:
        messages.error(request, "Session expired. Please register again.")
        return redirect('register')

    otp = generate_otp()
    request.session['otp'] = otp

    send_otp_email(data['email'], otp)

    messages.success(request, "OTP resent successfully!")
    return redirect('verify_otp')
