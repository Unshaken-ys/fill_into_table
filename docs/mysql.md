create database decorator_train;
use decorator_train;

-- 管理员表【登录/注册】
create table admin(
    username varchar(20) primary key,
    real_name varchar(20),
    password_hash varchar(200) not null
);

create table student(
    student_id varchar(4) primary key,
    student_name varchar(4) ,
    college varchar(20),
    gender varchar(2) 
); 

alter table student add class_condition varchar(10) default '未选课';
-- 课程表
create table course(
    course_id varchar(6) primary key,
    course_name varchar(30) not null,
    teacher varchar(10),
    credit int comment '学分'
);

-- 学生选课表【中间表，多对多】
create table student_course(
    student_id varchar(4),
    course_id varchar(6),
    score decimal(5,2) comment '考试分数',
    primary key(student_id,course_id),
    foreign key (student_id) references student(student_id)
        ON DELETE CASCADE
        ON UPDATE CASCADE,
    foreign key (course_id) references course(course_id)
        ON DELETE CASCADE
        ON UPDATE CASCADE
);

-- 任务清单表，关联admin管理员表
CREATE TABLE todo_task(
    task_id INT AUTO_INCREMENT PRIMARY KEY COMMENT '任务主键自增',
    username VARCHAR(20) NOT NULL COMMENT '所属管理员账号，关联admin表',
    task_text VARCHAR(200) NOT NULL COMMENT '任务内容',
    is_finished TINYINT DEFAULT 0 COMMENT '0未完成，1已完成',
    create_time DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    -- 外键关联管理员admin表
    FOREIGN KEY (username) REFERENCES admin(username)
        ON DELETE CASCADE
        ON UPDATE CASCADE
) COMMENT='管理员任务清单表';





drop trigger if exists tr_after_insert_student_course;

DELIMITER //
create trigger tr_after_insert_student_course
after insert on student_course
for each row
begin
    update student
    set class_condition = '已选课'
    where student_id = NEW.student_id
    and class_condition = '未选课';
end //
DELIMITER ;





