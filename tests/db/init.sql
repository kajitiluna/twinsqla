CREATE TABLE staff (
    account_id SERIAL PRIMARY KEY,
    username TEXT NOT NULL,
    age INTEGER NOT NULL
);

INSERT INTO staff(username, age) VALUES
    ('alice', 20), ('Bob', 21), ('Catalina', 41), ('Devid', 38), ('Evan', 14);