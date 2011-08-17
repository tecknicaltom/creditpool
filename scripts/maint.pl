#!/usr/bin/perl
#
# Credit Pool - Maintenance script
# $Id: maint.pl,v 1.2 2001/08/29 01:09:13 homic Exp $
#
# Copyright (C) 2001 Chuck Homic <homic@users.sourceforge.net>
#
# The Credit Pool is free software; you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by the Free
# Software Foundation; either version 2 of the License, or (at your option)
# any later version.
#
# This program and documentation is distributed in the hope that it will be
# useful, but without any warranty; without even the implied warranty of
# merchantability or fitness for a particular purpose. See the GNU General
# Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with the system, or one should be available above; if not, write to the
# Free Software Foundation, 59 Temple Place - Suite 330, Boston, MA
# 02111-1307, USA, or email homic@users.sourceforge.net.
#

use DBI;

$dbh=dbConnect();

$error = 0;

$query=$dbh->prepare("select sum(credit) as total from users");
$query->execute();

if ($query->rows()) {

	$ref=$query->fetchrow_hashref();

	$total=$ref->{'total'};

	if ($total == 0) {
		print "Credit pool total is zero.  Okay.\n";
	} else {
		print "ERROR!  Credit pool total is " . ::money($total) . ".\n";
		$error = 1;
	}
} else {
	print "ERROR!  Unable to sum user total.\n";
	$error=1;
}
print "\nChecking users:\n";

$query=$dbh->prepare("select name,credit from users");
$query->execute();
if ($query->rows()) {
	while ($ref=$query->fetchrow_hashref()) {
		$subquery=$dbh->prepare("select sum(credit) as total from trans_user where name=\"" . $ref->{'name'} . "\"");
		$subquery->execute();
		$subref=$subquery->fetchrow_hashref();

		$utotal = $ref->{'credit'};
		$xtotal = $subref->{'total'};
		
		print "\t$ref->{'name'} user(" . ::money($utotal) . ") xact(" . ::money($xtotal) . ")... ";
		if ($utotal == $xtotal) {
			print "Okay.\n";
		} else {
			print "ERROR!\n";
			$error = 1;
		}
	}
} else {
	print "ERROR!  No users.\n";
	$error=1;
}

$query=$dbh->prepare("select name from users where password != \"*\"");
$query->execute();
if ($query->rows()) {
	
	while ($ref=$query->fetchrow_hashref()) {
		$subquery=$dbh->prepare("select * from trans_user where entered < DATE_SUB(NOW(), INTERVAL 7 DAY) and status!=\"confirmed\" and name=\"$ref->{'name'}\"");
		$subquery->execute();
		
		if ($subquery->rows()) {
			print "\n$ref->{'name'} has unconfirmed transactions:\n";
			$email = ::getEmail($ref->{'name'});

			if ($email ne "") {
				print "(Sending report to $email)\n";
				open(MAIL, "|mail -s \"Unconfirmed Transactions\" $email");
			} else {
				print "(No email, suppressing report)\n";
				open (MAIL, ">/dev/null");
			}
			print MAIL "This is an automated message from your friendly local credit pool.\n";
			print MAIL "According to my records, you have had " . $subquery->rows() . " transactions unconfirmed\n";
			print MAIL "for more than 7 days:\n\n";
			
			while($subref=$subquery->fetchrow_hashref()) {
				$xquery=$dbh->prepare("select * from trans_global where xid=$subref->{'xid'}");
				$xquery->execute();
				$xref=$xquery->fetchrow_hashref();

				$dstr = "";
				$dstr .= "\t($subref->{'xid'}) ** ";
				$dstr .= ::money($subref->{'credit'}) . " ** ";
				$dstr .= "$xref->{'descrip'} ";
				$dstr .= "(" . ::timestamp($xref->{'entered'}) . ")";
				$dstr .= "\n";

				print $dstr;
				print MAIL $dstr;
			}

			print MAIL "\nPlease log into the credit pool to confirm that you have seen\n";
			print MAIL "these transactions.\n\n";
			print MAIL "http://callisto.vvisions.com/pool\n\n";
			print MAIL " -YOUR NAME HERE\n";
			close(MAIL);
		}
	}
}

sub getEmail {
	my $name = shift;
	my $query = $dbh->prepare("select email from users where name=\"$name\"");
	$query->execute();
	my $ref = $query->fetchrow_hashref();
	return $ref->{'email'};
}

sub dbConnect {
	my $dsn = "DBI:mysql:database=pool;host=localhost";
	my $dbh = DBI->connect($dsn, "pool", "<<<<PASSWORD>>>>") or 
		::fatal("Can't connect to database");
	return $dbh;
}

sub dbDisconnect {
	my $dbh = shift;
	$dbh->disconnect;
}

sub money {
	my $num = shift;
	my $ret;
	
	if ($num < 0 ) {
		$ret = sprintf("-\$%0.2f",abs($num/100));
	} else {
		$ret = sprintf("\$%0.2f",$num/100);
	}
	return $ret;
}

sub timestamp {
	my $stamp = shift;
	return $stamp;
}
