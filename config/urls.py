from django.contrib import admin
from django.contrib.auth.decorators import login_required
from django.urls import path
from django.views.generic import TemplateView
from accounts import access, views as a
from .health import health
from poetry import views as p
from memorization import views as m

urlpatterns = [
    path("healthz/", health, name="health"),
    path('admin/', admin.site.urls),
    path('login/', access.username_access, name='login'),
    path('logout/', access.sign_out, name='logout'),
    path('signup/', access.username_access, {'signup': True}, name='signup'),
    path('login/confirm/', access.confirm_browser, name='confirm-browser'),
    path('settings/', a.settings_page, name='settings'),
    path('settings/photo/', a.profile_photo, name='profile-photo'),
    path('settings/photo/remove/', a.remove_profile_photo, name='profile-photo-remove'),
    path('', p.dashboard, name='dashboard'),
    path('poems/', p.poem_list, name='poems'),
    path('poems/new/', p.poem_edit, name='poem-new'),
    path('poems/<int:pk>/', p.poem_detail, name='poem-detail'),
    path('poems/<int:pk>/edit/', p.poem_edit, name='poem-edit'),
    path('poems/<int:pk>/archive/', p.archive, name='poem-archive'),
    path('poems/<int:pk>/restore/', p.archive, {'restore': True}, name='poem-restore'),
    path('poems/<int:pk>/topics/', p.assign_tags, name='poem-tags'),
    path('topics/', p.tags, name='tags'),
    path('topics/view/<str:slug>/', p.poem_list, name='tag-detail'),
    path('topics/new/', p.tag_change, name='tag-new'),
    path('topics/<int:pk>/rename/', p.tag_change, {'action': 'rename'}, name='tag-rename'),
    path('topics/<int:pk>/delete/', p.tag_change, {'action': 'delete'}, name='tag-delete'),
    path('poems/<int:pk>/tags/', p.assign_tags),
    path('tags/', p.tags),
    path('tags/view/<str:slug>/', p.poem_list),
    path('tags/new/', p.tag_change),
    path('tags/<int:pk>/rename/', p.tag_change, {'action': 'rename'}),
    path('tags/<int:pk>/delete/', p.tag_change, {'action': 'delete'}),
    path('poets/', p.poets, name='poets'),
    path('treasury/', login_required(TemplateView.as_view(template_name='poetry/treasury.html')), name='treasury'),
    path('favorites/', p.favorites, name='favorites'),
    path('verses/<int:pk>/favorite/', p.favorite, name='favorite'),
    path('verses/<int:pk>/unfavorite/', p.favorite, {'remove': True}, name='unfavorite'),
    path('memorize/', m.items, name='memorize'),
    path('memorize/items/', m.add_item, name='item-new'),
    path('memorize/items/<int:pk>/pause/', m.item_action, {'action': 'pause'}, name='item-pause'),
    path('memorize/items/<int:pk>/resume/', m.item_action, {'action': 'resume'}, name='item-resume'),
    path('memorize/items/<int:pk>/delete/', m.item_action, {'action': 'delete'}, name='item-delete'),
    path('review/', m.review, name='review'),
    path('review/<int:pk>/rate/', m.rate, name='rate'),
    path('discover/', p.discover, name='discover'),
    path('api/discover/random/', p.discover, {'api': True}, name='random-poem'),
    path('design-system/', login_required(TemplateView.as_view(template_name='design_system.html')), name='design-system'),
]
