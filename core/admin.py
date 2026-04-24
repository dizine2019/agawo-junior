from django.contrib import admin
from import_export.admin import ImportExportModelAdmin
from import_export import resources, fields
from .models import Student, Mark

# =========================
# STUDENT RESOURCE
# =========================
class StudentResource(resources.ModelResource):
    full_name = fields.Field(column_name='Full Name')

    class Meta:
        model = Student
        fields = ('full_name', 'admission_number', 'grade')
        export_order = ('full_name', 'admission_number', 'grade')

    def dehydrate_full_name(self, student):
        # Combine first and last name into one field
        return f"{student.first_name} {student.last_name}"

# =========================
# STUDENT ADMIN
# =========================
@admin.register(Student)
class StudentAdmin(ImportExportModelAdmin):
    resource_class = StudentResource
    list_display = ('first_name', 'last_name', 'admission_number', 'grade')
    search_fields = ('first_name', 'last_name', 'admission_number')
    list_filter = ('grade',)

# =========================
# MARK ADMIN
# =========================
@admin.register(Mark)
class MarkAdmin(ImportExportModelAdmin):
    list_display = ('student', 'subject', 'marks', 'term', 'year')
    search_fields = ('student__first_name', 'student__last_name', 'subject')
    list_filter = ('subject', 'term', 'year')
