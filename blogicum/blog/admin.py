from django.contrib import admin

from .models import Category, Comment, Location, Post


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ('text', 'author', 'post', 'created_at')
    search_fields = ('text', 'author__username')
    list_select_related = ('author', 'post')


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('title', 'slug', 'is_published', 'created_at')
    list_editable = ('is_published',)
    list_filter = ('is_published',)
    search_fields = ('title', 'description')
    prepopulated_fields = {'slug': ('title',)}


@admin.register(Location)
class LocationAdmin(admin.ModelAdmin):
    list_display = ('name', 'is_published', 'created_at')
    list_editable = ('is_published',)
    list_filter = ('is_published',)
    search_fields = ('name',)


@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = (
        'title', 'author', 'category', 'location', 'pub_date', 'is_published',
    )
    list_editable = ('is_published',)
    list_filter = ('is_published', 'category', 'location', 'pub_date')
    search_fields = ('title', 'text', 'author__username')
    list_select_related = ('author', 'category', 'location')
    date_hierarchy = 'pub_date'
