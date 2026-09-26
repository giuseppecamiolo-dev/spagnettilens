#!/usr/bin/perl -w

use strict;
use CGI;
use DBI;

my $q = CGI->new;
print $q->header('text/html');

print <<HTML;
<html>
<head><title>Generatore Fatture S-GeO</title></head>
<body>
<h1>Dettaglio Fattura Studente</h1>
HTML

my $student_code = $q->param('student_code');
my $total_amount = 0;

if (!$student_code) {
    print "<p>Errore: Nessun codice studente fornito.</p></body></html>";
    exit;
}

# Connessione al database
my $dbh = DBI->connect("DBI:mysql:database=sgeo;host=localhost", "admin", "password", {'RaiseError' => 1});

# Vulnerabilità: Interpolazione diretta della variabile SQL
my $sql = "SELECT id, description, amount FROM invoices WHERE student_code = '$student_code' AND status = 'pending'";
my $sth = $dbh->prepare($sql);
$sth->execute();

print "<table border='1'><tr><th>ID</th><th>Descrizione</th><th>Importo</th></tr>";

while (my $ref = $sth->fetchrow_hashref()) {
    print "<tr>";
    print "<td>" . $ref->{'id'} . "</td>";
    print "<td>" . $ref->{'description'} . "</td>";
    print "<td>" . $ref->{'amount'} . " &euro;</td>";
    print "</tr>";
    
    $total_amount += $ref->{'amount'};
}

print "</table>";
print "<br><b>Totale da pagare: $total_amount &euro;</b>";
print "</body></html>";

$sth->finish();
$dbh->disconnect();
