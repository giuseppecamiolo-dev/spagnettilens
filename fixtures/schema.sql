-- Schema fixture for SpaghettiLens-AI (S-GeO Invoices & IH Course Bookings)

CREATE TABLE IF NOT EXISTS invoices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_code VARCHAR(32) NOT NULL,
    description VARCHAR(255) NOT NULL,
    amount DECIMAL(10, 2) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'pending'
);

CREATE TABLE IF NOT EXISTS enrollments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL,
    course_name VARCHAR(128) NOT NULL,
    booking_date DATE NOT NULL
);

-- Seed test rows including decimal edge cases (0.10 + 0.20) for parity verification
INSERT INTO invoices (id, student_code, description, amount, status) VALUES
    (101, 'STU-2026-01', 'Quota Iscrizione Annuale', 120.10, 'pending'),
    (102, 'STU-2026-01', 'Modulo Conversazione B2', 250.20, 'pending'),
    (103, 'STU-2026-01', 'Materiale Didattico (Pagato)', 45.00, 'paid');

INSERT INTO enrollments (id, student_id, course_name, booking_date) VALUES
    (1, 42, 'IELTS Preparation Intensive', '2026-10-01'),
    (2, 42, 'Business English C1', '2026-10-15');
