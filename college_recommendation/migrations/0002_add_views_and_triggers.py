from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('college_recommendation', '0001_initial'),
    ]

    operations = [
        # Create a view for college statistics grouped by city and course
        migrations.RunSQL(
            """
            CREATE VIEW college_city_course_stats AS
            SELECT 
                city,
                course_name,
                COUNT(*) as college_count,
                AVG(percentile) as avg_percentile,
                MIN(percentile) as min_percentile,
                MAX(percentile) as max_percentile
            FROM college_recommendation_college
            GROUP BY city, course_name
            ORDER BY city, course_name;
            """,
            reverse_sql="DROP VIEW IF EXISTS college_city_course_stats;"
        ),
        
        # Create a view for category-wise college distribution
        migrations.RunSQL(
            """
            CREATE VIEW college_category_distribution AS
            SELECT 
                category,
                COUNT(*) as college_count,
                AVG(percentile) as avg_percentile
            FROM college_recommendation_college
            GROUP BY category
            ORDER BY college_count DESC;
            """,
            reverse_sql="DROP VIEW IF EXISTS college_category_distribution;"
        ),
        
        # Create a table to log college data changes
        migrations.RunSQL(
            """
            CREATE TABLE college_data_log (
                id INT AUTO_INCREMENT PRIMARY KEY,
                college_id INT,
                action VARCHAR(10),
                old_data JSON,
                new_data JSON,
                changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """,
            reverse_sql="DROP TABLE IF EXISTS college_data_log;"
        ),
        
        # Create a trigger to log college data changes (INSERT)
        migrations.RunSQL(
            """
            CREATE TRIGGER college_insert_trigger
            AFTER INSERT ON college_recommendation_college
            FOR EACH ROW
            INSERT INTO college_data_log (college_id, action, new_data)
            VALUES (
                NEW.id, 
                'INSERT',
                JSON_OBJECT(
                    'college_code', NEW.college_code,
                    'college_name', NEW.college_name,
                    'course_code', NEW.course_code,
                    'course_name', NEW.course_name,
                    'category', NEW.category,
                    'merit_rank', NEW.merit_rank,
                    'percentile', NEW.percentile,
                    'city', NEW.city
                )
            );
            """,
            reverse_sql="DROP TRIGGER IF EXISTS college_insert_trigger;"
        ),
        
        # Create a trigger to log college data changes (UPDATE)
        migrations.RunSQL(
            """
            CREATE TRIGGER college_update_trigger
            AFTER UPDATE ON college_recommendation_college
            FOR EACH ROW
            INSERT INTO college_data_log (college_id, action, old_data, new_data)
            VALUES (
                NEW.id,
                'UPDATE',
                JSON_OBJECT(
                    'college_code', OLD.college_code,
                    'college_name', OLD.college_name,
                    'course_code', OLD.course_code,
                    'course_name', OLD.course_name,
                    'category', OLD.category,
                    'merit_rank', OLD.merit_rank,
                    'percentile', OLD.percentile,
                    'city', OLD.city
                ),
                JSON_OBJECT(
                    'college_code', NEW.college_code,
                    'college_name', NEW.college_name,
                    'course_code', NEW.course_code,
                    'course_name', NEW.course_name,
                    'category', NEW.category,
                    'merit_rank', NEW.merit_rank,
                    'percentile', NEW.percentile,
                    'city', NEW.city
                )
            );
            """,
            reverse_sql="DROP TRIGGER IF EXISTS college_update_trigger;"
        ),
        
        # Create a trigger to log college data changes (DELETE)
        migrations.RunSQL(
            """
            CREATE TRIGGER college_delete_trigger
            AFTER DELETE ON college_recommendation_college
            FOR EACH ROW
            INSERT INTO college_data_log (college_id, action, old_data)
            VALUES (
                OLD.id,
                'DELETE',
                JSON_OBJECT(
                    'college_code', OLD.college_code,
                    'college_name', OLD.college_name,
                    'course_code', OLD.course_code,
                    'course_name', OLD.course_name,
                    'category', OLD.category,
                    'merit_rank', OLD.merit_rank,
                    'percentile', OLD.percentile,
                    'city', OLD.city
                )
            );
            """,
            reverse_sql="DROP TRIGGER IF EXISTS college_delete_trigger;"
        ),
        
        # Create a table to maintain college count statistics
        migrations.RunSQL(
            """
            CREATE TABLE college_statistics (
                id INT AUTO_INCREMENT PRIMARY KEY,
                stat_name VARCHAR(50),
                stat_value INT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
            );
            """,
            reverse_sql="DROP TABLE IF EXISTS college_statistics;"
        ),
        
        # Insert initial statistics
        migrations.RunSQL(
            """
            INSERT INTO college_statistics (stat_name, stat_value)
            VALUES ('total_colleges', (SELECT COUNT(*) FROM college_recommendation_college));
            """,
            reverse_sql="DELETE FROM college_statistics WHERE stat_name = 'total_colleges';"
        ),
        
        # Create a trigger to maintain college count statistics
        migrations.RunSQL(
            """
            CREATE TRIGGER college_count_trigger
            AFTER INSERT ON college_recommendation_college
            FOR EACH ROW
            INSERT INTO college_statistics (stat_name, stat_value)
            VALUES ('total_colleges', (SELECT COUNT(*) FROM college_recommendation_college))
            ON DUPLICATE KEY UPDATE 
                stat_value = (SELECT COUNT(*) FROM college_recommendation_college),
                updated_at = CURRENT_TIMESTAMP;
            """,
            reverse_sql="DROP TRIGGER IF EXISTS college_count_trigger;"
        ),
    ]