USE ERP_DB;

-- Xóa bảng nếu tồn tại
IF EXISTS (SELECT * FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME = 'projects_project_required_departments')
BEGIN
    DROP TABLE projects_project_required_departments;
END