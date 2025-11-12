from django.shortcuts import render
from django.http import JsonResponse, HttpResponse
from django.contrib.auth.decorators import login_required
from .models import College
from django.db import connection
import csv
import io
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, A4, landscape

@login_required
def search_colleges(request):
    """
    Handle college search requests.
    Filters colleges based on percentile, category, courses, and cities.
    Returns JSON response with matching colleges.
    """
    if request.method == 'POST':
        try:
            # Get form data
            percentile = float(request.POST.get('percentile', 0))
            category = request.POST.get('category', '')
            courses = request.POST.getlist('course')
            cities = request.POST.getlist('cities')
            
            # Handle "All Courses" selection
            if '' in courses or not courses:
                courses = []  # Empty list means all courses
            
            # Handle "All Cities" selection
            if '' in cities or not cities:
                cities = []  # Empty list means all cities
            
            # Define percentile range (±5)
            min_percentile = percentile - 10
            max_percentile = percentile + 10
            
            # Map user-friendly category names to database category codes
            category_mapping = {
                'General': ['GOPENS', 'GOPENH', 'GOPENO'],
                'OBC': ['GOBCS', 'GOBCH', 'GOBCO', 'GSEBCS', 'GSEBCH', 'GSEBCO'],
                'SC': ['GSCS', 'GSCH', 'SCS', 'SCH'],
                'ST': ['GSTS', 'GSTH', 'STS', 'STH']
            }
            
            # Get the list of category codes to match
            category_codes = category_mapping.get(category, [])
            
            # Build the database query
            colleges_query = College.objects.all()
            
            # Filter by category if specified
            if category and category_codes:
                colleges_query = colleges_query.filter(category__in=category_codes)
            
            # Filter by percentile range
            colleges_query = colleges_query.filter(percentile__gte=min_percentile, percentile__lte=max_percentile)
            
            # Filter by courses if specific courses are selected
            if courses:
                colleges_query = colleges_query.filter(course_name__in=courses)
            
            # Filter by cities if specific cities are selected
            if cities:
                colleges_query = colleges_query.filter(city__in=cities)
            
            # Execute the query and convert to list of dictionaries
            matching_colleges = []
            for college in colleges_query:
                matching_colleges.append({
                    'college_code': college.college_code,
                    'college_name': college.college_name,
                    'course_code': college.course_code,
                    'course_name': college.course_name,
                    'category': college.category,
                    'merit_rank': college.merit_rank,
                    'percentile': str(college.percentile),  # Convert to string for JSON serialization
                    'city': college.city
                })
            
            # Sort colleges by percentile (descending) and then by merit rank (ascending)
            matching_colleges.sort(key=lambda x: (-float(x['percentile']), int(x['merit_rank'])))
            
            # Store results in session for download
            request.session['search_results'] = matching_colleges
            request.session['search_criteria'] = {
                'percentile': percentile,
                'category': category,
                'courses': courses,
                'cities': cities
            }
            
            # Get additional statistics from our database views
            stats_data = {}
            if matching_colleges:
                with connection.cursor() as cursor:
                    # Get city-course statistics for the matching results
                    college_ids = [str(c.get('id', 0)) for c in matching_colleges if c.get('id')]
                    if college_ids:
                        cursor.execute("""
                            SELECT city, COUNT(*) as college_count
                            FROM college_recommendation_college
                            WHERE id IN ({})
                            GROUP BY city
                            ORDER BY college_count DESC
                            LIMIT 5
                        """.format(','.join(['%s'] * len(college_ids))), college_ids)
                        city_stats = cursor.fetchall()
                        stats_data['top_cities'] = [{'city': row[0], 'count': row[1]} for row in city_stats]
                    
                    # Get category distribution for matching results
                    cursor.execute("""
                        SELECT category, COUNT(*) as college_count
                        FROM college_recommendation_college
                        WHERE id IN ({})
                        GROUP BY category
                        ORDER BY college_count DESC
                    """.format(','.join(['%s'] * len(college_ids))), college_ids)
                    category_stats = cursor.fetchall()
                    stats_data['category_distribution'] = [{'category': row[0], 'count': row[1]} for row in category_stats]
            
            # Return JSON response with enhanced data
            return JsonResponse({
                'success': True,
                'colleges': matching_colleges,
                'stats': stats_data
            })
            
        except Exception as e:
            # Handle any errors
            return JsonResponse({
                'success': False,
                'error': str(e)
            })
    
    # If not POST request, return error
    return JsonResponse({
        'success': False,
        'error': 'Invalid request method'
    })

@login_required
def download_colleges(request):
    """
    Download college search results as CSV file.
    """
    # Get results from session
    results = request.session.get('search_results', [])
    criteria = request.session.get('search_criteria', {})
    
    # Enhance with statistics from our database views
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT city, course_name, college_count, avg_percentile
            FROM college_city_course_stats 
            ORDER BY college_count DESC
            LIMIT 5
        """)
        stats = cursor.fetchall()
    
    if not results:
        return HttpResponse(b"No results to download.", content_type="text/plain")
    
    # Create CSV response
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="college_recommendations.csv"'
    
    # Create CSV writer
    writer = csv.writer(response)
    
    # Write header
    writer.writerow([
        'College Code', 'College Name', 'Course Code', 'Course Name', 
        'Category', 'Merit Rank', 'Percentile', 'City'
    ])
    
    # Write data rows
    for college in results:
        writer.writerow([
            college['college_code'],
            college['college_name'],
            college['course_code'],
            college['course_name'],
            college['category'],
            college['merit_rank'],
            college['percentile'],
            college['city']
        ])
    
    return response

@login_required
def download_colleges_pdf(request):
    """
    Download college search results as PDF file.
    """
    # Get results from session
    results = request.session.get('search_results', [])
    criteria = request.session.get('search_criteria', {})
    
    # Enhance with statistics from our database views
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT city, course_name, college_count, avg_percentile
            FROM college_city_course_stats 
            ORDER BY college_count DESC
            LIMIT 5
        """)
        stats = cursor.fetchall()
    
    if not results:
        return HttpResponse(b"No results to download.", content_type="text/plain")
    
    # Create PDF response
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="college_recommendations.pdf"'
    
    # Create PDF document with adjusted margins for better table display
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, 
        pagesize=landscape(A4),  # Use landscape orientation
        rightMargin=10,  # Further reduced margins
        leftMargin=10,   # Further reduced margins
        topMargin=10,    # Further reduced margins
        bottomMargin=10   # Further reduced margins
    )
    elements = []
    
    # Get styles and create custom styles
    styles = getSampleStyleSheet()
    
    # Title style
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=20,
        spaceAfter=25,
        alignment=1,  # Center alignment
        textColor=colors.HexColor('#1E40AF'),  # Professional blue color
        fontName='Helvetica-Bold'
    )
    
    # Subtitle style
    subtitle_style = ParagraphStyle(
        'CustomSubtitle',
        parent=styles['Heading2'],
        fontSize=12,
        spaceAfter=20,
        alignment=1,  # Center alignment
        textColor=colors.HexColor('#4B5563'),  # Gray color
        fontName='Helvetica'
    )
    
    # Criteria style
    criteria_style = ParagraphStyle(
        'Criteria',
        parent=styles['Normal'],
        fontSize=10,
        spaceAfter=25,
        leading=12,  # Line spacing
        textColor=colors.HexColor('#1F2937'),  # Dark gray
        fontName='Helvetica'
    )
    
    # Section header style
    section_style = ParagraphStyle(
        'SectionHeader',
        parent=styles['Heading3'],
        fontSize=12,
        spaceAfter=15,
        textColor=colors.HexColor('#1E40AF'),  # Professional blue
        fontName='Helvetica-Bold'
    )
    
    # College card style
    card_style = ParagraphStyle(
        'CardStyle',
        parent=styles['Normal'],
        fontSize=8,
        spaceAfter=10,
        leading=10,
        textColor=colors.HexColor('#1F2937'),
        fontName='Helvetica'
    )
    
    # Add title
    title = Paragraph("College Recommendation Report", title_style)
    elements.append(title)
    
    # Add subtitle with date
    from datetime import datetime
    subtitle = Paragraph(f"Generated on {datetime.now().strftime('%B %d, %Y at %I:%M %p')}", subtitle_style)
    elements.append(subtitle)
    
    # Add search criteria with better formatting
    if criteria:
        criteria_parts = []
        if 'percentile' in criteria:
            criteria_parts.append(f"<b>Percentile:</b> {criteria['percentile']}")
        if 'category' in criteria:
            criteria_parts.append(f"<b>Category:</b> {criteria['category']}")
        if criteria.get('courses'):
            courses_list = ', '.join(criteria['courses'])
            criteria_parts.append(f"<b>Courses:</b> {courses_list}")
        if criteria.get('cities'):
            cities_list = ', '.join(criteria['cities'])
            criteria_parts.append(f"<b>Cities:</b> {cities_list}")
        
        criteria_text = "<br/>".join(criteria_parts)
        criteria_paragraph = Paragraph(criteria_text, criteria_style)
        elements.append(criteria_paragraph)
    
    # Add section header
    section_header = Paragraph(f"Matching Colleges ({len(results)} found)", section_style)
    elements.append(section_header)
    
    # Create table data with headers
    table_data = [
        ['College Code', 'College Name', 'Course Name', 'Ctg.', 'Rank', 'Percentile', 'City']
    ]
    
    # Add data rows
    for i, college in enumerate(results):
        table_data.append([
            college['college_code'],
            college['college_name'],
            college['course_name'],
            college['category'],
            str(college['merit_rank']),
            college['percentile'],
            college['city']
        ])
    
    # Create table with further adjusted column widths to fully show City column
    table = Table(
        table_data, 
        colWidths=[25, 370, 260, 30, 30, 40, 130],  # Further reduced other columns, maximized City column
        repeatRows=1,  # Repeat header on each page
        hAlign='LEFT'  # Align table to left
    )
    
    # Apply table styling with forced text wrapping
    table.setStyle(TableStyle([
        # Header row styling
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1E40AF')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 8),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
        ('TOPPADDING', (0, 0), (-1, 0), 8),
        
        # Data rows styling - focus on text fitting
        ('ALIGN', (0, 1), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 6),  # Very small font for maximum fit
        ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#E5E7EB')),
        
        # Alternate row colors
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.whitesmoke, colors.white]),
        
        # Minimal padding for maximum text space
        ('TOPPADDING', (0, 1), (-1, -1), 2),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 2),
        
        # Specific column alignments
        ('ALIGN', (1, 1), (1, -1), 'LEFT'),  # College name
        ('ALIGN', (2, 1), (2, -1), 'LEFT'),  # Course name
        ('ALIGN', (6, 1), (6, -1), 'LEFT'),  # City
        ('ALIGN', (0, 1), (0, -1), 'CENTER'),  # College code
        ('ALIGN', (3, 1), (5, -1), 'CENTER'),  # Category, Merit Rank, Percentile
        
        # Force text wrapping and prevent single line overflow
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('WORDWRAP', (0, 0), (-1, -1)),
        ('LEADING', (0, 1), (-1, -1), 7),
        
        # Force column-specific wrapping
        ('WORDWRAP', (1, 1), (1, -1)),  # College name
        ('WORDWRAP', (2, 1), (2, -1)),  # Course name
        
        # Ensure proper alignment
        ('ALIGN', (0, 1), (-1, -1), 'LEFT'),
        ('ALIGN', (0, 0), (0, 0), 'CENTER'),  # Header center alignment
        ('ALIGN', (3, 1), (5, -1), 'CENTER'),  # Numerical columns center alignment
    ]))
    
    elements.append(table)
    
    # Build PDF with proper page break handling
    doc.build(elements)
    
    # Get PDF content
    pdf_content = buffer.getvalue()
    buffer.close()
    
    response.write(pdf_content)
    return response
