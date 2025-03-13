from django.contrib import admin
from .models import KeywordResponse, SMSRecipient, ScheduledMessage
from django.utils.html import format_html


# Define the admin for KeywordResponse
class KeywordResponseAdmin(admin.ModelAdmin):
    # Display fields in the list view
    list_display = ('icon_preview', 'trigger_word', 'response_text', 'priority', 'notify_owner', 'edit_delete_actions')

    # Icon preview field (render the icon as an image or placeholder)
    def icon_preview(self, obj):
        if obj.icon:  # Check if the icon exists
            return format_html('<img src="{}" width="30" height="30" />', obj.icon.url)
        return "No Icon"

    # Custom actions (Edit/Delete buttons)
    def edit_delete_actions(self, obj):
        return format_html(
            '<a class="button" href="/admin/bot/keywordresponse/{}/change/">Edit</a> '
            '<a class="button" style="color:red;" href="/admin/bot/keywordresponse/{}/delete/">Delete</a>',
            obj.id, obj.id
        )

    # Actions (to be used in the admin)
    edit_delete_actions.short_description = "Actions"

    search_fields = ('trigger_word', 'response_text')
    list_filter = ('priority', 'notify_owner')
    ordering = ['priority']


# Define the admin for SMSRecipient
class SMSRecipientAdmin(admin.ModelAdmin):
    list_display = ('name', 'phone', 'is_active', 'edit_delete_actions')

    def edit_delete_actions(self, obj):
        return format_html(
            '<a class="button" href="/admin/bot/smsrecipient/{}/change/">Edit</a> '
            '<a class="button" style="color:red;" href="/admin/bot/smsrecipient/{}/delete/">Delete</a>',
            obj.id, obj.id
        )

    search_fields = ('name', 'phone')
    list_filter = ('is_active',)


# Define the admin for ScheduledMessage
class ScheduledMessageAdmin(admin.ModelAdmin):
    list_display = ('content', 'interval_hours', 'order', 'is_active', 'image_preview', 'edit_delete_actions')

    # Display the image in the list view
    def image_preview(self, obj):
        if obj.image:
            return format_html('<img src="{}" width="30" height="30" />', obj.image.url)
        return "No Image"

    # Custom actions (Edit/Delete buttons)
    def edit_delete_actions(self, obj):
        return format_html(
            '<a class="button" href="/admin/bot/scheduledmessage/{}/change/">Edit</a> '
            '<a class="button" style="color:red;" href="/admin/bot/scheduledmessage/{}/delete/">Delete</a>',
            obj.id, obj.id
        )

    search_fields = ('content',)
    list_filter = ('is_active',)




# Register the models with the admin site
admin.site.register(KeywordResponse, KeywordResponseAdmin)
admin.site.register(SMSRecipient, SMSRecipientAdmin)
admin.site.register(ScheduledMessage, ScheduledMessageAdmin)
