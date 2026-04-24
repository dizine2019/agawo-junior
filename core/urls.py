# urls.py
from django.contrib import admin
from django.urls import path
from core import views

urlpatterns = [
    path('admin/', admin.site.urls),

    # ================= AUTHENTICATION =================
    path('', views.login_view, name='login'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),

    # ================= DASHBOARD =================
    path('dashboard/', views.dashboard, name='dashboard'),

    # ================= STUDENT MANAGEMENT =================
    # View students by grade (e.g., /grades/7/)
    path('grades/<int:grade>/', views.grade_students, name='grade_students'),
    path('student/add/', views.add_student, name='add_student'), 
    path('student/<int:student_id>/edit/', views.edit_student, name='edit_student'),
    path('student/<int:student_id>/delete/', views.delete_student, name='delete_student'),

    # ================= ASSESSMENT & MARKS =================
    # The menu/landing page for marks
    path('marks-entry/', views.marks_entry, name='marks_entry'),
    # The actual scoring page (add_mark.html)
    path('marks/add/', views.add_mark, name='add_mark'),

    # ================= RANKING & PDF REPORTS =================
    # The full performance summary/ranking list
    path('marks/view-list/', views.view_list, name='view_list'),
    
    # NEW: Download the full Ranking List as a PDF Result Sheet
    path('marks/view-list/pdf/', views.download_view_list_pdf, name='download_view_list_pdf'),

    # Individual Student Report Card (Web and PDF)
    path('report-card/<int:student_id>/', views.generate_report_card, name='generate_report_card'),
    
    # Helper for specific individual PDF trigger
    path('marks/download-pdf/', views.download_pdf, name='download_pdf'),

    # ================= MODULES =================
    path('library/', views.library, name='library'), 
    # the Library links 
    path("course-books/", views.course_books, name="course_books"),
    path("story-books/", views.story_books, name="story_books"),
    path("schemes/", views.schemes, name="schemes"),


    #-----------------------------------------------------
    path('reports/', views.reports, name='reports'),
    path('fees/', views.fees, name='fees'),
    path('report-card/<int:id>/', views.report_card, name='report_card'),

    #--------------for teachers Profile-----------
    path('teachers/', views.teachers, name='teachers')




]
