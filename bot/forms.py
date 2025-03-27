from django import forms
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import PasswordChangeForm
from django import forms

User = get_user_model()


class EmailOrUsernameAuthForm(AuthenticationForm):
    username = forms.CharField(label='Email or Username')

    def clean_username(self):
        username = self.cleaned_data.get('username')
        if '@' in username:
            try:
                username = User.objects.get(email=username).username
            except User.DoesNotExist:
                pass
        return username


# class AvatarUpdateForm(forms.ModelForm):
#     class Meta:
#         model = UserProfile
#         fields = ['avatar']


class ProfileUpdateForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email']


# class NotificationPreferenceForm(forms.ModelForm):
#     class Meta:
#         model = UserProfile
#         fields = ['email_notifications', 'push_notifications']
