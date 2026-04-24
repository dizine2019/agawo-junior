from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.db.models import Q, Sum, Avg
from django.http import HttpResponse
from django.template.loader import get_template

# PDF Generation Imports
from xhtml2pdf import pisa
import io
import datetime  # Essential for dynamic year logic
from .models import Student, Mark

# =====================================
# HELPERS & CBC RUBRIC LOGIC (8 LEVELS)
# =====================================

def get_grade_num(grade_string):
    """Extracts numeric grade (e.g., 'Grade 5' -> '5')"""
    try:
        return str(grade_string).split()[-1]
    except (IndexError, AttributeError):
        return "1"

def is_admin(user):
    """Check if user is staff"""
    return user.is_staff

def get_subjects_for_grade(grade_string):
    """Returns official CBC subjects based on Kenya Curriculum levels"""
    try:
        num = int(get_grade_num(grade_string))
        if 1 <= num <= 3: 
            return ["Maths", "English", "Kiswahili", "Creative Art", "Environmental", "Religious Education"]
        elif 4 <= num <= 6: 
            return ["Maths", "English", "Science", "Social Studies", "Agriculture", "Home Science"]
        else: 
            return ["Maths", "English", "Integrated Science", "Pretechnical Studies", "CRE", "Kiswahili", "Agriculture", "Social Studies", "Creative Arts"]
    except (ValueError, TypeError):
        return []

def get_cbc_rubric_data(mark):
    """Official 8-level CBC grading logic with auto-generated comments"""
    if mark is None: return {'code': 'N/A', 'label': 'No Data', 'comment': 'No assessment recorded.'}
    if mark >= 90:
        return {'code': 'EE1', 'label': 'Exceeding Expectation 1', 'comment': 'Exemplary mastery and innovation.'}
    elif mark >= 80:
        return {'code': 'EE2', 'label': 'Exceeding Expectation 2', 'comment': 'Excellent! Proficient beyond expected levels.'}
    elif mark >= 65:
        return {'code': 'ME1', 'label': 'Meeting Expectation 1', 'comment': 'Very Good. Confidently meets all learning outcomes.'}
    elif mark >= 50:
        return {'code': 'ME2', 'label': 'Meeting Expectation 2', 'comment': 'Good progress. Meets requirements with minimal help.'}
    elif mark >= 40:
        return {'code': 'AE1', 'label': 'Approaching Expectation 1', 'comment': 'Fair. Performs tasks with occasional guidance.'}
    elif mark >= 30:
        return {'code': 'AE2', 'label': 'Approaching Expectation 2', 'comment': 'Developing. Needs more practice.'}
    elif mark >= 15:
        return {'code': 'BE1', 'label': 'Below Expectation 1', 'comment': 'Struggling. Requires remedial support.'}
    else:
        return {'code': 'BE2', 'label': 'Below Expectation 2', 'comment': 'Needs intensive individualized attention.'}

# =====================================
# AUTHENTICATION
# =====================================

def login_view(request):
    if request.user.is_authenticated:
        return redirect("dashboard")
    if request.method == "POST":
        user = authenticate(request, username=request.POST.get("username"), password=request.POST.get("password"))
        if user:
            login(request, user)
            messages.success(request, f"Welcome back, {user.username}!")
            return redirect("dashboard")
        messages.error(request, "Invalid username or password.")
    return render(request, "login.html")

@login_required
def logout_view(request):
    logout(request)
    messages.info(request, "Logged out successfully.")
    return redirect("login")

@login_required
def dashboard(request):
    return render(request, "dashboard.html")

# =====================================
# STUDENT MANAGEMENT
# =====================================

@login_required
@user_passes_test(is_admin)
def add_student(request):
    if request.method == "POST":
        Student.objects.create(
            first_name=request.POST.get("first_name"),
            last_name=request.POST.get("last_name"),
            admission_number=request.POST.get("admission_number"),
            grade=request.POST.get("grade"),
            parent_name=request.POST.get("parent_name"),
            parent_phone=request.POST.get("parent_phone"),
            assessment_number=request.POST.get("assessment_number"),
            year_of_birth=request.POST.get("year_of_birth") or None
        )
        messages.success(request, "Student added successfully!")
        return redirect("dashboard")
    return render(request, "add_student.html", {"grades": [f"Grade {i}" for i in range(1, 10)]})

@login_required
def grade_students(request, grade):
    grade_name = f"Grade {grade}"
    students = Student.objects.filter(grade=grade_name)
    return render(request, "grade_students.html", {"grade": grade, "students": students})

@login_required
def edit_student(request, student_id):
    student = get_object_or_404(Student, id=student_id)
    if request.method == "POST":
        student.first_name = request.POST.get("first_name")
        student.last_name = request.POST.get("last_name")
        student.grade = request.POST.get("grade")
        student.save()
        return redirect("dashboard")
    return render(request, "edit_student.html", {"student": student})

@login_required
def delete_student(request, student_id):
    student = get_object_or_404(Student, id=student_id)
    student.delete()
    return redirect("dashboard")

# =====================================
# ASSESSMENT & RANKING LOGIC
# =====================================

@login_required
def marks_entry(request):
    return render(request, "marks_entry.html")

@login_required
def add_mark(request):
    """The scoring page where marks are entered"""
    grades = [f"Grade {i}" for i in range(1, 10)]
    
    # DYNAMIC YEAR LIST (Showing up to 10 years into the future)
    current_year = datetime.datetime.now().year
    years = [str(y) for y in range(2024, current_year + 11)] 
    
    sel_grade = request.GET.get("grade")
    sel_sub = request.GET.get("subject")
    term = request.GET.get("term", "1")
    year = request.GET.get("year", str(current_year))
    search_query = request.GET.get("search", "")
    
    subjects = get_subjects_for_grade(sel_grade) if sel_grade else []
    
    students = Student.objects.filter(grade=sel_grade) if sel_grade else []
    if search_query:
        students = students.filter(
            Q(first_name__icontains=search_query) | 
            Q(last_name__icontains=search_query) | 
            Q(admission_number__icontains=search_query)
        )

    marks_qs = Mark.objects.filter(subject=sel_sub, term=term, year=year)
    marks_map = {m.student_id: m.marks for m in marks_qs}

    if request.method == "POST":
        action = request.POST.get("action")
        try:
            out_of = float(request.POST.get("out_of") or 100.0)
        except ValueError:
            out_of = 100.0
            
        if action == "bulk_save":
            for s in students:
                val = request.POST.get(f"marks_{s.id}")
                if val and val.strip() != "":
                    perc = (float(val) / out_of) * 100
                    Mark.objects.update_or_create(
                        student=s, subject=sel_sub, term=term, year=year,
                        defaults={"marks": int(round(perc))}
                    )
            messages.success(request, f"Assessment marks for {sel_sub} saved.")
        return redirect(f"/marks/add/?grade={sel_grade}&subject={sel_sub}&term={term}&year={year}")

    return render(request, "add_mark.html", {
        "grades": grades, "years": years, "subjects": subjects, "students": students, 
        "marks_map": marks_map, "selected_grade": sel_grade, 
        "selected_subject": sel_sub, "term": term, "year": year
    })

@login_required
def view_list(request):
    """Web view for the Performance Ranking List"""
    grades = [f"Grade {i}" for i in range(1, 10)]
    terms = ["1", "2", "3"]
    
    # DYNAMIC YEAR LIST (Showing up to 10 years into the future)
    current_year = datetime.datetime.now().year
    years = [str(y) for y in range(2024, current_year + 11)]
    
    sel_grade = request.GET.get("grade", "Grade 1")
    sel_term = request.GET.get("term", "1")
    sel_year = request.GET.get("year", str(current_year))
    
    subjects = get_subjects_for_grade(sel_grade)
    students_query = Student.objects.filter(grade=sel_grade)
    
    performance_data = []
    for student in students_query:
        marks_qs = Mark.objects.filter(student=student, term=sel_term, year=sel_year)
        total = marks_qs.aggregate(Sum('marks'))['marks__sum'] or 0
        avg = marks_qs.aggregate(Avg('marks'))['marks__avg'] or 0
        
        subject_marks = []
        marks_dict = {m.subject: m.marks for m in marks_qs}
        for sub in subjects:
            score = marks_dict.get(sub)
            rubric_info = get_cbc_rubric_data(score) if score is not None else None
            subject_marks.append({
                'score': score,
                'rubric': rubric_info['code'] if rubric_info else None
            })
        
        overall = get_cbc_rubric_data(avg)
        performance_data.append({
            'student': student,
            'subject_marks': subject_marks,
            'total': total,
            'overall_rubric': overall['code'] if overall else "N/A",
            'rubric_label': overall['label'] if overall else ""
        })
    
    performance_data = sorted(performance_data, key=lambda x: x['total'], reverse=True)

    return render(request, "view_list.html", {
        "grades": grades, "terms": terms, "years": years,
        "performance_data": performance_data, "subjects": subjects,
        "selected_grade": sel_grade, "selected_term": sel_term, "selected_year": sel_year,
        "is_pdf": False
    })

# =====================================
# PDF GENERATION
# =====================================

@login_required
def report_card(request, id):
    """Generates the Portrait Single-Page PDF report card"""
    student = get_object_or_404(Student, id=id)
    term = request.GET.get('term', '1')
    year = request.GET.get('year', str(datetime.datetime.now().year))
    
    marks_qs = Mark.objects.filter(student=student, term=term, year=year)
    total_marks = marks_qs.aggregate(Sum('marks'))['marks__sum'] or 0
    average_marks = marks_qs.aggregate(Avg('marks'))['marks__avg'] or 0
    
    # Calculate Out Of based on number of assessed subjects
    subject_count = marks_qs.count()
    total_possible = subject_count * 100
    
    subjects_data = []
    for m in marks_qs:
        subjects_data.append({
            'subject': m.subject,
            'score': m.marks,
            'rubric': get_cbc_rubric_data(m.marks)
        })
        
    overall_performance = get_cbc_rubric_data(average_marks)

    context = {
        'student': student, 'marks': subjects_data, 'total': total_marks,
        'total_possible': total_possible, 'average': round(average_marks, 2),
        'overall': overall_performance, 'term': term, 'year': year,
    }

    template = get_template('report_card_pdf.html')
    html = template.render(context)
    result = io.BytesIO()
    pisa.pisaDocument(io.BytesIO(html.encode("UTF-8")), result)
    
    return HttpResponse(result.getvalue(), content_type='application/pdf')

@login_required
def download_view_list_pdf(request):
    """Generates the Landscape PDF Ranking List"""
    response = view_list(request)
    context = response.context_data
    context['is_pdf'] = True
    
    template = get_template('view_list.html')
    html = template.render(context)
    result = io.BytesIO()
    pisa.pisaDocument(io.BytesIO(html.encode("UTF-8")), result)
    
    response = HttpResponse(result.getvalue(), content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="Ranking_{context["selected_grade"]}.pdf"'
    return response

# URL COMPATIBILITY HELPERS
@login_required
def generate_report_card(request, student_id): return report_card(request, id=student_id)
@login_required
def download_pdf(request): return HttpResponse("OK")
@login_required
def library(request): return render(request, "library.html")
@login_required
def reports(request): return render(request, "reports.html")
@login_required
def fees(request): return render(request, "fees.html")


from django.shortcuts import render

def library(request):
    return render(request, "library.html")

def course_books(request):
    return render(request, "course_books.html")

def story_books(request):
    return render(request, "story_books.html")

def schemes(request):
    return render(request, "schemes.html")

# for teachers

def teachers(request):
    return render(request, 'teachers.html')
