<?php
// booking_legacy.php - Scritto circa nel 2008
session_start();

$db_host = "localhost";
$db_user = "root";
$db_pass = "secret";
$db_name = "ih_booking_db";

// Connessione deprecata
$conn = mysql_connect($db_host, $db_user, $db_pass) or die("Errore connessione");
mysql_select_db($db_name, $conn);

$student_id = $_GET['id'];
$course_name = $_POST['course'];
$booking_date = date("Y-m-d");

// Vulnerabilità: SQL Injection classica, nessun escaping
$sql = "INSERT INTO enrollments (student_id, course_name, booking_date) 
        VALUES ($student_id, '$course_name', '$booking_date')";

if($_POST['submit']) {
    $result = mysql_query($sql, $conn);
    if($result) {
        $msg = "Prenotazione salvata con successo!";
    } else {
        $msg = "Errore: " . mysql_error();
    }
}
?>
<html>
<head><title>Prenotazione Corsi</title></head>
<body>
    <h2>Gestione Prenotazioni</h2>
    <?php if(isset($msg)) echo "<div style='color:red;'>$msg</div>"; ?>
    <form method="POST" action="booking_legacy.php?id=<?php echo $student_id; ?>">
        Corso: <input type="text" name="course" />
        <input type="submit" name="submit" value="Prenota" />
    </form>
    <hr>
    <h3>I tuoi corsi:</h3>
    <?php
    // Query di lettura senza controllo errori
    $res = mysql_query("SELECT course_name FROM enrollments WHERE student_id = $student_id");
    while($row = mysql_fetch_assoc($res)) {
        echo "<li>" . $row['course_name'] . "</li>";
    }
    ?>
</body>
</html>
