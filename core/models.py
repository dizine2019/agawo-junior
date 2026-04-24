from django.db import models

# =========================
# STUDENT MODEL
# =========================
class Student(models.Model):
    GRADE_CHOICES = [(f"Grade {i}", f"Grade {i}") for i in range(1, 10)]

    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    admission_number = models.CharField(max_length=20, unique=True)
    grade = models.CharField(max_length=20, choices=GRADE_CHOICES)
    
    # NEW FIELDS ADDED
    parent_name = models.CharField(max_length=200, blank=True, null=True)
    parent_phone = models.CharField(max_length=15, blank=True, null=True)
    assessment_number = models.CharField(max_length=50, blank=True, null=True)
    year_of_birth = models.IntegerField(blank=True, null=True)

    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.admission_number})"


# =========================
# MARK MODEL
# =========================
class Mark(models.Model):
    SUBJECT_CHOICES = [
        ("Maths", "Maths"),
        ("English", "English"),
        ("Kiswahili", "Kiswahili"),
        ("Integrated Science", "Integrated Science"),
        ("Agriculture", "Agriculture"),
        ("Social Studies", "Social Studies"),
        ("CRE", "CRE"),
        ("Creative Art", "Creative Art"),
        ("Pretechnical Studies", "Pretechnical Studies"),
        ("Creative Arts", "Creative Arts"),
    ]

    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    subject = models.CharField(max_length=50, choices=SUBJECT_CHOICES)
    marks = models.IntegerField(default=0)
    term = models.IntegerField(default=1)
    year = models.IntegerField(default=2026)

    class Meta:
        unique_together = ('student', 'subject', 'term', 'year')

    def __str__(self):
        return f"{self.student} - {self.subject} - {self.marks}"

