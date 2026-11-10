#!/usr/bin/perl -w

use strict;
use CGI;
use DBI;

my $q = CGI->new;
print $q->header('text/html');

print <<HTML;
<html>
<head><title>S-GeO Invoice Generator</title></head>
<body>
<h1>Student Invoice Details</h1>
HTML

my $student_code = $q->param('student_code');
my $total_amount = 0;

if (!$student_code) {
    print "<p>Error: No student code provided.</p></body></html>";
    exit;
}

# Database connection
my $dbh = DBI->connect("DBI:mysql:database=sgeo;host=localhost", "admin", "password", {'RaiseError' => 1});

# Vulnerability: Direct SQL variable interpolation
my $sql = "SELECT id, description, amount FROM invoices WHERE student_code = '$student_code' AND status = 'pending'";
my $sth = $dbh->prepare($sql);
$sth->execute();

print "<table border='1'><tr><th>ID</th><th>Description</th><th>Amount</th></tr>";

while (my $ref = $sth->fetchrow_hashref()) {
    print "<tr>";
    print "<td>" . $ref->{'id'} . "</td>";
    print "<td>" . $ref->{'description'} . "</td>";
    print "<td>" . $ref->{'amount'} . " &euro;</td>";
    print "</tr>";
    
    $total_amount += $ref->{'amount'};
}

print "</table>";
print "<br><b>Total due: $total_amount &euro;</b>";
print "</body></html>";

$sth->finish();
$dbh->disconnect();
