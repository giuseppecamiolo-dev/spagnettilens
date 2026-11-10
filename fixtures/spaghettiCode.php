<?php
// booking_legacy.php - Written around 2008
session_start();

$db_host = "localhost";
$db_user = "root";
$db_pass = "secret";
$db_name = "ih_booking_db";

// Deprecated database connection
$conn = mysql_connect($db_host, $db_user, $db_pass) or die("Connection error");
mysql_select_db($db_name, $conn);

$student_id = $_GET['id'];
$course_name = $_POST['course'];
$booking_date = date("Y-m-d");

// Vulnerability: Classic SQL Injection, no escaping
$sql = "INSERT INTO enrollments (student_id, course_name, booking_date) 
        VALUES ($student_id, '$course_name', '$booking_date')";

if($_POST['submit']) {
    $result = mysql_query($sql, $conn);
    if($result) {
        $msg = "Booking saved successfully!";
    } else {
        $msg = "Error: " . mysql_error();
    }
}
?>
<html>
<head><title>Course Booking</title></head>
<body>
    <h2>Booking Management</h2>
    <?php if(isset($msg)) echo "<div style='color:red;'>$msg</div>"; ?>
    <form method="POST" action="booking_legacy.php?id=<?php echo $student_id; ?>">
        Course: <input type="text" name="course" />
        <input type="submit" name="submit" value="Book" />
    </form>
    <hr>
    <h3>Your courses:</h3>
    <?php
    // Read query without error checking
    $res = mysql_query("SELECT course_name FROM enrollments WHERE student_id = $student_id");
    while($row = mysql_fetch_assoc($res)) {
        echo "<li>" . $row['course_name'] . "</li>";
    }
    ?>
</body>
</html>
