CREATE TABLE base_staff (
    staff_id SERIAL PRIMARY KEY,
    username TEXT NOT NULL,
    age INTEGER
);

INSERT INTO base_staff(staff_id, username, age) VALUES
    (1, 'Alice', 20), (2, 'Bob', 21), (3, 'Catalina', 41), (4, 'Devid', 38), (5, 'Evan', 14),
    (6, 'Flanky', 73), (7, 'George', 55), (8, 'Helen', 32), (9, 'Idea', 18), (10, 'Jack', NULL);