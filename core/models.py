from django.db import models
from datetime import date


# =====================================================
# SHARED CHOICES
# =====================================================

SUBJECT_CHOICES = [
    ("Mathematics", "Mathematics"),
    ("English", "English"),
    ("Kiswahili", "Kiswahili"),
    ("Integrated Science", "Integrated Science"),
    ("Social Studies", "Social Studies"),
    ("Religious Education", "Religious Education"),
    ("Pre-Technical Studies", "Pre-Technical Studies"),
    ("Health Education", "Health Education"),
    ("Creative Arts & Sports", "Creative Arts & Sports"),
    ("Agriculture & Nutrition", "Agriculture & Nutrition"),
]

GRADE_CHOICES = [
    (f"Grade {i}", f"Grade {i}")
    for i in range(1, 10)
]


# =====================================================
# TEACHER MODEL
# =====================================================

class Teacher(models.Model):

    name = models.CharField(
        max_length=100,
        unique=True
    )

    phone = models.CharField(
        max_length=15,
        blank=True,
        null=True
    )

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


# =====================================================
# STUDENT MODEL
# =====================================================

class Student(models.Model):

    student_name = models.CharField(
        max_length=200
    )

    admission_number = models.CharField(
        max_length=20,
        unique=True
    )

    grade = models.CharField(
        max_length=20,
        choices=GRADE_CHOICES
    )

    parent_name = models.CharField(
        max_length=200,
        blank=True,
        null=True
    )

    parent_phone = models.CharField(
        max_length=15,
        blank=True,
        null=True
    )

    class Meta:
        ordering = ["student_name"]

    def __str__(self):
        return f"{self.student_name} ({self.admission_number})"


# =====================================================
# ALLOCATION MODEL
# =====================================================

class Allocation(models.Model):

    teacher = models.ForeignKey(
        Teacher,
        on_delete=models.CASCADE,
        related_name="allocations"
    )

    subject = models.CharField(
        max_length=100,
        choices=SUBJECT_CHOICES
    )

    grade = models.CharField(
        max_length=20,
        choices=GRADE_CHOICES
    )

    singles = models.PositiveIntegerField(
        default=0
    )

    doubles = models.PositiveIntegerField(
        default=0
    )

    total_lessons = models.PositiveIntegerField(
        default=0
    )

    class Meta:
        ordering = ["teacher", "grade"]

    def save(self, *args, **kwargs):

        self.total_lessons = (
            self.singles +
            (self.doubles * 2)
        )

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.teacher.name} - {self.subject} ({self.grade})"


# =====================================================
# MARKS MODEL
# =====================================================

class Mark(models.Model):

    student = models.ForeignKey(
        Student,
        on_delete=models.CASCADE,
        related_name="marks"
    )

    subject = models.CharField(
        max_length=100,
        choices=SUBJECT_CHOICES
    )

    marks = models.PositiveIntegerField(
        default=0
    )

    term = models.PositiveIntegerField(
        default=1
    )

    year = models.PositiveIntegerField(
        default=date.today().year
    )

    class Meta:

        unique_together = (
            "student",
            "subject",
            "term",
            "year"
        )

        ordering = [
            "student",
            "subject"
        ]

    def __str__(self):

        return (
            f"{self.student.student_name} "
            f"- {self.subject} "
            f"({self.marks})"
        )


# =====================================================
# BOOK MODEL
# =====================================================

class Book(models.Model):

    title = models.CharField(
        max_length=200
    )

    author = models.CharField(
        max_length=100,
        blank=True,
        null=True
    )

    total_copies = models.PositiveIntegerField(
        default=1
    )

    available_copies = models.PositiveIntegerField(
        default=1
    )

    class Meta:
        ordering = ["title"]

    def save(self, *args, **kwargs):

        if not self.pk:
            self.available_copies = self.total_copies

        super().save(*args, **kwargs)

    def __str__(self):
        return self.title


# =====================================================
# BORROW RECORD MODEL
# =====================================================

class BorrowRecord(models.Model):

    MEMBER_TYPES = (
        ("Student", "Student"),
        ("Teacher", "Teacher"),
    )

    STATUS = (
        ("Borrowed", "Borrowed"),
        ("Returned", "Returned"),
        ("Overdue", "Overdue"),
    )

    member_name = models.CharField(
        max_length=200
    )

    member_type = models.CharField(
        max_length=10,
        choices=MEMBER_TYPES
    )

    book = models.ForeignKey(
        Book,
        on_delete=models.CASCADE,
        related_name="borrow_records"
    )

    copies = models.PositiveIntegerField(
        default=1
    )

    borrow_date = models.DateField(
        default=date.today
    )

    due_date = models.DateField()

    return_date = models.DateField(
        blank=True,
        null=True
    )

    status = models.CharField(
        max_length=10,
        choices=STATUS,
        default="Borrowed"
    )

    class Meta:
        ordering = ["-borrow_date"]

    def save(self, *args, **kwargs):

        if (
            self.status == "Borrowed" and
            self.due_date < date.today()
        ):
            self.status = "Overdue"

        super().save(*args, **kwargs)

    def __str__(self):

        return (
            f"{self.member_name} "
            f"- {self.book.title}"
        )


# =====================================================
# FINE MODEL
# =====================================================

class Fine(models.Model):

    record = models.OneToOneField(
        BorrowRecord,
        on_delete=models.CASCADE,
        related_name="fine"
    )

    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0
    )

    is_paid = models.BooleanField(
        default=False
    )

    class Meta:
        ordering = ["id"]

    def __str__(self):

        status = (
            "Paid"
            if self.is_paid
            else "Unpaid"
        )

        return f"Fine: {self.amount} ({status})"