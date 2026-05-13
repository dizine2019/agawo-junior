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
    path('grades/<int:grade>/', views.grade_students, name='grade_students'),
    path('student/add/', views.add_student, name='add_student'), 
    path('student/<int:student_id>/edit/', views.edit_student, name='edit_student'),
    path('student/<int:student_id>/delete/', views.delete_student, name='delete_student'),
    path('add-students-bulk/', views.add_students_bulk, name='add_students_bulk'),

    # ================= ASSESSMENT & MARKS =================
    path('marks-entry/', views.marks_entry, name='marks_entry'),
    path('marks/add/', views.add_mark, name='add_mark'),

    # ================= RANKING & REPORTS =================
    path('marks/view-list/', views.view_list, name='view_list'),
    path('marks/view-list/pdf/', views.download_view_list_pdf, name='download_view_list_pdf'),
    path('report-card/<int:id>/', views.report_card, name='report_card'),

    # ================= TEACHERS & ALLOCATION =================
    path('teachers/', views.teachers, name='teachers'),
    path('add_teacher/', views.teachers, name='add_teacher'), 
    path('delete_teacher/<int:teacher_id>/', views.delete_teacher, name='delete_teacher'),
    path('teachers/registry/', views.teachers_registry, name='teachers_registry'),
    path('allocate/', views.lesson_allocation, name='lesson_allocation'),

    # ================= LIBRARY ERP =================
    # This single path handles the page load AND the Borrow/Return AJAX logic
    path('library/', views.library, name='library'), 
    # This path is kept for the optional standalone return logic
    path('library/return/<int:record_id>/', views.return_book, name='return_book'),

    # ================= OTHER MODULES =================
    path("course-books/", views.course_books, name="course_books"),
    path("story-books/", views.story_books, name="story_books"),
    path("schemes/", views.schemes, name="schemes"),
    path('reports/', views.reports, name='reports'),
    path('fees/', views.fees, name='fees'),
    path('timetable/generate/', views.generate_timetable, name='generate_timetable'),
]
