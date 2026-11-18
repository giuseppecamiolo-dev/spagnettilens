#!/usr/bin/perl
# legacy_invoice_batch.pl - Legacy ERP Batch Invoicing & Settlement Script
use strict;
use CGI;
use DBI;

my $q = CGI->new;
my $dbh = DBI->connect("DBI:mysql:database=erp_db;host=localhost", "root", "pass123");

my $customer_id = $q->param('cust_id');
my $discount_pct = $q->param('discount') || 0.0;
my $action = $q->param('action');

print $q->header('text/html');

if ($action eq 'settle_invoices') {
    # VULNERABILITY 1: Direct SQL Injection via unparameterized string interpolation
    my $sql = "SELECT id, amount, tax_rate FROM invoices WHERE customer_id = '$customer_id' AND status = 'OPEN'";
    my $sth = $dbh->prepare($sql);
    $sth->execute();

    my $total_settled = 0.0;
    while (my @row = $sth->fetchrow_array()) {
        my ($inv_id, $amount, $tax_rate) = @row;
        
        # BUG 2: IEEE-754 floating-point arithmetic on currency (requires Decimal in FastAPI)
        my $discounted = $amount * (1.0 - ($discount_pct / 100.0));
        my $final_with_tax = $discounted + ($discounted * $tax_rate);
        $total_settled += $final_with_tax;

        # VULNERABILITY 3: Second-order SQLi / unescaped update without transaction boundary
        $dbh->do("UPDATE invoices SET status = 'PAID', settled_amount = $final_with_tax WHERE id = $inv_id");
    }

    # VULNERABILITY 4: Reflected XSS via unescaped CGI param output
    print "<h2>Settlement Complete for Customer: $customer_id</h2>";
    print "<p>Total Charged: EUR " . sprintf("%.2f", $total_settled) . "</p>";
}
