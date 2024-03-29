#!/usr/bin/perl
#
# Credit Pool - Main CGI interface
# $Id: index.cgi,v 1.5 2007/01/25 23:17:42 homic Exp $
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

use strict;
use warnings;
use diagnostics;
use DBI;
use CGI qw(:standard);
#use Chart::Lines;
#use Chart::Bars;

sub escapedPrintf(@)
{
	my $format = shift;
	$format =~ s/(?<!\\)\%m/<span class="money">%d<\/span>/g;
	my @params = map { ::armorHTMLString($_) } @_;
	my $output = sprintf($format, @params);
	$output =~ s#(<span class="money)(">)(-?\d+)(</span>)#{
		sprintf("$1%s$2%s\$%0.2f$4",
			$3 < 0 ? ' negative' : '',
			$3 < 0 ? '-' : '',
			abs($3)/100);
	}#ge;
	print $output;
}

my $dbh=dbConnect();
my $cgi=CGI->new();

# Throw some globals
my $name = $cgi->param('name');
my $password = $cgi->param('password');
my $action = $cgi->param('action');

#HACK: render a chart before we generate text/html
if ($action eq "Chart") {
	::drawChart();
	exit;
}

if ($action eq "Volume") {
	::drawChart2();
	exit;
}

# special case... allow no password for password change
if ($cgi->param('passwordChange')) {
	::passwordChangeForm();
	::footer();
	exit;
}

my $session_status = ::confirmSession();
if ($session_status eq 'none')
{
	# No session... present login screen
	::login();
	exit;
}

if ($session_status eq 'expire') {
	print '<h3>Session expired</h3>';
	print 'You\'ll need to re-login to continue<hr />';
	::login();
	exit;
}

if ($action eq '' || $action eq "summary") {
	::printHeader();
	::summary();
	::footer();
	exit;
}

if ($action eq "Change History") {
	::summary();
	::footer();
	exit;
}

if ($action eq "Confirm Selected") {
	::confirmSelected();
	::summary();
	::footer();
	exit;
}

if ($action eq "Confirm All") {
	::confirmAll();
	::summary();
	::footer();
	exit;
}

if ($action eq "Select Users") {
	::printHeader();
	::enterTransData();
	::footer();
	exit;
}

if ($action eq "Submit Transaction") {
	::printHeader();
	::confirmTrans();
	::footer();
	exit;
}

if ($action eq "Confirmed") {
	::finalizeTrans();
	::summary();
	::footer();
	exit;
}

if ($action eq "Change Password") {
	::passwordCommit();
	::login();
	exit;
}

# Might not be an action
if ($action eq 'viewTrans' && $cgi->param('viewTrans') ne '') {
	::viewTrans($cgi->param('viewTrans'));
	::footer();
	exit;
}


::fatal("No code for what you're doing!");
exit;

sub login {

	print <<'EOF';
<body bgcolor=black text=white>
<img src="icons/credit-pool.jpg"><p>
Please identify yourself.
<form action="" method="post">
<table>
<tr><td>User ID<td><input type="text" name="name" size=15 maxlength=15 />
<tr><td>Password<td><input type="password" name="password" size=15 maxlength=8 />
<tr><td><td><input type="submit" name="submit" value="Log in" />
</table>
<input type="hidden" name="action" value="summary" />
<hr /><input type="submit" name="passwordChange" value="Change Password" />
</form></body>
EOF

}
sub summary {
	my $query=$dbh->prepare('select * from users where name=?');
	$query->execute($name);
	my $ref=$query->fetchrow_hashref();
	my $history = $cgi->param('history');

	if ($history eq "") {
		$history = 7;
	}
	print '<body bgcolor=black text=white>', "\n";
	print '<img src="icons/cp-small.jpg" align=right>', "\n";

	
	escapedPrintf('<h1>Summary Report for %s %s</h1>', $ref->{'firstname'}, $ref->{'lastname'});

	my $bal = $ref->{'credit'};

	$query=$dbh->prepare('select * from trans_user where name=? and status="pending"');
	$query->execute($name);

	escapedPrintf '<h3>Current balance: %m</h3>', $bal;

	if ($bal < 0) {
		escapedPrintf 'This means the credit pool owes you %m.', abs($bal);
	} else {
		escapedPrintf 'This means you owe %m to the credit pool.', $bal;
	}


	print '<form action="" method="post">';

	if ($query->rows()) {
		print '<hr /><h3>Unconfirmed transactions</h3>', "\n";
		::transList($query,1);
		print '<p>(Confirming a transaction means that you\'ve seen it, not necessarily that you agree to it.  If you would like to contest a transaction, take it up with the transaction creator, in the "Who did it?" column.)';
	} else {
		#print ("No pending transactions.\n");
	}

	print '<hr /><h3>New transaction</h3>', "\n";
	
	::newTransForm();

	if ($history == 7) {
		print '<hr /><h3>The week in review</h3>', "\n";
	} else {
		print '<hr /><h3>Some time ago...</h3>', "\n";
	}

	escapedPrintf('These are the transactions from the past <input type="text" name="history" value="%d" size=3 maxlength=5 /> days:<br />', $history);
	print '<input type="submit" name="action" value="Change History" /><p>', "\n";

	$query=$dbh->prepare('select * from trans_user where name=? and entered > DATE_SUB(NOW(), INTERVAL ? DAY)');
	$query->execute($name, $history);
	if ($query->rows()) {
		::transList($query,0);
	}

	print '<hr />', "\n";
	print '<h3>Totals</h3>', "\n";

	$query=$dbh->prepare('select firstname,lastname,credit from users where flags like "%exists%" order by credit');
	$query->execute();

	print '<table border=1>';
	my $sum = 0;
	my $users = 0;
	while ($ref=$query->fetchrow_hashref()) {
		my $value = $ref->{'credit'};
		print '<tr>';
		escapedPrintf('<td>%s %s</td>', $ref->{'firstname'}, $ref->{'lastname'});
		escapedPrintf('<td>%m</td>', $value);
		print '</tr>';
		$sum += abs($value);
		$users++;
	}
	$sum /= 2;
	print '</table>';
	escapedPrintf '<p>Total imbalance: %m<br />', $sum;
	escapedPrintf 'Average imbalance: %m<br />', $sum / $users;

	$query=$dbh->prepare('select sum(abs(credit)) as total from trans_user');
	$query->execute();
	$ref=$query->fetchrow_hashref();
	escapedPrintf('Total throughput: %m<br />', $ref->{'total'}/2);
	print '<hr /><h3>Charts (Holy alpha, Batman!)</h3>Draw a chart for somebody:<br />';
	print '<input type="text" name="chartme" value="" size=16 maxlength=16 />  ';
	print '<input type="submit" name="action" value="Chart" />';
	print '<p>Or just look at this one: ';
	print '<input type="submit" name="action" value="Volume" />';
	
	print '</form>';
}

sub transList {
	my $query = shift;
	my $confirm = shift;

	print '<table border=1>';
	print '<tr>';
	if ($confirm) {
		print '<th>Confirm?</th>';
	}
	print '<th>ID</th>';
	print '<th>Date entered</th>';
	#print '<th>Transaction date</th>';
	print '<th>Cost</th>';
	print '<th>Description</th>';
	print '<th>Who did it?</th>';
	print '</tr>';

	my $ref=$query->fetchrow_hashref();
	while($ref) {
		my $g_query=$dbh->prepare('select * from trans_global where xid=?');
		$g_query->execute($ref->{'xid'});
		my $g_ref=$g_query->fetchrow_hashref();
		print '<tr>';
		if ($confirm) {
			escapedPrintf('<td align=center><input type="checkbox" name="confirm" value="%s" /></td>', $ref->{'xid'});
		}
		escapedPrintf('<td><a href="?action=viewTrans&amp;viewTrans=%s">%s</a></td>', $ref->{'xid'}, $ref->{'xid'});
		escapedPrintf('<td>%s</td>', $g_ref->{'entered'});
		#print "<td>$g_ref->{'date'}</td>";
		escapedPrintf('<td>%m</td>', $ref->{'credit'});
		escapedPrintf('<td>%s</td>', $g_ref->{'descrip'});
		escapedPrintf('<td>%s</td>', ::fullName($g_ref->{'creator'}));
		$ref=$query->fetchrow_hashref();
	}
	print '</table><p>';
	if ($confirm) {
		print '<input type="submit" name="action" value="Confirm Selected" />';
		print '<input type="submit" name="action" value="Confirm All" />';
	}
}

sub newTransForm() {
	my $query=$dbh->prepare('select name,lastname,firstname from users where flags like "%exists%" order by firstname,lastname,name');
	$query->execute();
	print '<select multiple name="sucker">';
	while (my $ref=$query->fetchrow_hashref()) {
		if ($ref->{'name'} ne $name) {
			my ($fullname) = ($ref->{'firstname'} . ' ' . $ref->{'lastname'}) =~ /\s*\b(.*)\b\s*/;
			escapedPrintf('  <option value="%s">%s - %s</option>', $ref->{'name'}, $fullname, $ref->{'name'});
		}
	}
	print '</select>';
	print '<br />';
	print '<input type="submit" name="action" value="Select Users" />';
}

sub confirmSelected {
	my @confirm=$cgi->param('confirm');
	my $i;

	my $query=$dbh->prepare('update trans_user set status="confirmed" where name=? and xid=?');
	for ($i = 0; $i <= $#confirm; $i++) {
		$query->execute($name, $confirm[$i]);
	}
}

sub confirmAll{
	my $query=$dbh->prepare('update trans_user set status="confirmed" where name=?');
	$query->execute($name);
}

sub enterTransData {
	my @suckers = $cgi->param('sucker');
	my $i;
	my @bad;
	my @good;

	if ($#suckers == -1) {
		userError("You didn't actually pick anyone.");
	}

	::progressHeader(1);
	print '<h1>Transaction Data</h1>';
	print '<form action="" method="post">';
	print '<table border=1>';

	print '<tr>';
	print '<th>Name</th>';
	print '<th>...owes this much</th>';
	print '</tr>';
	
	my $query=$dbh->prepare('select lastname,firstname from users where flags like "%exists%" and name=?');
	for ($i = 0; $i <= $#suckers; $i++) {
		$query->execute($suckers[$i]);
		my $ref=$query->fetchrow_hashref();

		if ($ref) {
			print '<tr>';
			escapedPrintf('<td>%s %s</td>', $ref->{'firstname'}, $ref->{'lastname'});
			if ($suckers[$i] ne $name) {
				escapedPrintf('<td><input type="text" name="val_%s" value="" /></td>', $suckers[$i]);
			} else {
				print '<td>N/A</td>';
			}
			print '</tr>';
			push @good, $suckers[$i];
		} else {
			print '<tr>';
			escapedPrintf('<td><font color=red>%s</font></td>', $suckers[$i]);
			print '<td>N/A</td>';
			print '</tr>';
			#$bad .= "<li><tt>" . $suckers[$i] . "</tt>\n";
			push @bad, $suckers[$i];
		}
	}
	
	print '</table>';
	print '(You may enter arithmetic, for example "(22.05 + 5.22) / 3")';

	if (@bad) {
		print '<h2><font color=red>Error!</font></h2>';
		print 'I don\'t have any record of:';
		print '<blockquote><ul>';
		for my $bad_input (@bad) {
			escapedPrintf('<li><tt>%s</tt></li>', $bad_input);
		}
		print '</ul></blockquote>';
		print 'Hit the BACK button to try again';
		if (@good) {
			print ', or charge ahead if you want.';
		} else {
			print '.';
		}
	}

	if (@good) {
		print '<p>Description:<br /><input type="text" name="descrip" value="" size="50" maxlength="100" /><p>';
		escapedPrintf('<input type="hidden" name="suckerlist" value="%s" />', join(' ', @good));
		print '<p><input type="submit" name="action" value="Submit Transaction" />';
	}

	print '</form>';
}

sub confirmTrans {
	my $descrip = $cgi->param('descrip');
	my $suckerlist = $cgi->param('suckerlist');
	my $i;
	my $val;
	my $sum = 0;

	if ($descrip eq "") {
		userError("You must enter a transaction description.");
	}

	my @suckers = split(/ /, $suckerlist);
	
	if ($#suckers == -1) {
		::fatal("No one's in the list?");
	}

	::progressHeader(2);
	print '<h1>Transaction Confirmation</h1>';

	my $query=$dbh->prepare('select NOW() as time');
	$query->execute();
	my $ref=$query->fetchrow_hashref();

	print '<form action="" method="post">';
	escapedPrintf('<input type="hidden" name="descrip" value="%s" />', $descrip);
	escapedPrintf('<h2>%s (%s)</h2>', $descrip, $ref->{'time'});

	escapedPrintf('<input type="hidden" name="suckerlist" value="%s" />', $suckerlist);

	print '<table border=1>';

	print '<tr>';
	print '<th>Name</th>';
	print '<th>Owes</th>';
	print '</tr>';

	$query=$dbh->prepare('select lastname,firstname from users where flags like "%exists%" and name=?');
	for ($i = 0; $i <= $#suckers; $i++) {
		$query->execute($suckers[$i]);
		$ref=$query->fetchrow_hashref();

		$val = $cgi->param("val_$suckers[$i]");
		# remove $ signs
		$val =~ s/\$//g;
		if ($val =~ /^[\d\s\+\-\*\/\(\)\.]*$/)
		{
			$val = eval($val);
		}
		else 
		{ 
			$val = 0; 
		}

		$val = eval($val);
		$val = int($val * 100) / 100;
		$sum += $val * 100;

		print '<tr>';
		escapedPrintf('<td>%s %s</td>', $ref->{'firstname'}, $ref->{'lastname'});
		escapedPrintf('<td>%m</td>', $val*100);
		escapedPrintf('<input type="hidden" name="val_%s" value="%s" />', $suckers[$i], $val);
		print '</tr>';
	}
	
	print '</table><p>';
	escapedPrintf('This means your credit for this transaction is %m.<br />', -$sum);

	$query=$dbh->prepare('select credit from users where name=?');
	$query->execute($name);
	$ref=$query->fetchrow_hashref();

	escapedPrintf('Your new balance will be %m.', $ref->{'credit'} - $sum);
	
	print '<p><input type="submit" name="action" value="Confirmed" />';
	print '</form>';
}

sub verifyFinalizeIntegrity {
	my $suckerlist = shift;
	my @suckers = split(/ /, $suckerlist);
	my $confirm;
	my $error = 0;

	my $query = $dbh->prepare('select name from users where flags like "%exists%" and name=?');
	for (my $i = 0; $i <= $#suckers; $i++) {
		my $val = $cgi->param("val_$suckers[$i]") * 100;

		# verify existance of user
		$query->execute($suckers[$i]);
		if ($query->rows() != 1) {
			::nonFatalUserError("User \"$suckers[$i]\" does not exist");
			$error = 1;
		} else {
			$confirm = $query->fetchrow_hashref()->{'name'};
			if ($confirm ne $suckers[$i]) {
				::fatal("Big internal problem in verifyFinalize");
			}
		}

		if ($val == 0 && $name ne $suckers[$i]) {
			::nonFatalUserError("No money value given for user \"$suckers[$i]\"");
			$error = 1;
		}

	}

	if ($error) {
		::nonFatalUserError("");
		::nonFatalUserError("You should fix your submission and resubmit.");
		::nonFatalUserError("The submission was NOT added to the database.");
		exit;
	} else {
		# do nothing... go on with life
	}
}

sub finalizeTrans {
	my $descrip = $cgi->param('descrip');
	my $suckerlist = $cgi->param('suckerlist');
	my $i;
	my $val;
	my $sum = 0;

	if ($descrip eq "") {
		userError("You must enter a transaction description.");
	}

	my @suckers = split(/ /, $suckerlist);
	
	if ($#suckers == -1) {
		::fatal("No one's in the list?");
	}

	::verifyFinalizeIntegrity($suckerlist);

	my $query=$dbh->prepare('insert trans_global (creator,descrip) values(?, ?)');
	$query->execute($name, ::unArmorHTMLString($descrip));

	$query=$dbh->prepare('select LAST_INSERT_ID() as id');
	$query->execute();
	my $xid=$query->fetchrow_hashref()->{'id'};
	
	$query=$dbh->prepare('insert trans_user (xid,name,credit) values (?, ?, ?)');
	for ($i = 0; $i <= $#suckers; $i++) {
		$val = $cgi->param("val_$suckers[$i]") * 100;
		$sum += $val;
		
		if ($val != 0) {
			$query->execute($xid, $suckers[$i], $val);

			::addToCredit($suckers[$i],$val);
		}
	}

	# Primary user gets remainder
	if ($sum != 0) {
		$sum = -$sum;

		$query=$dbh->prepare('insert trans_user (xid,name,credit,status) values (?, ?, ?,"confirmed")');
		$query->execute($xid, $name, $sum);

		::addToCredit($name, $sum);
	}
	return $xid;
}

sub addToCredit {
	my $uid= shift;
	my $inc = shift;
	my $query;
	my $val;
	
	$query=$dbh->prepare('select credit from users where name=?');
	$query->execute($uid);
	$val=$query->fetchrow_hashref()->{'credit'};
	
	$val += $inc;

	$query=$dbh->prepare('update users set credit=? where name=?');
	$query->execute($val, $uid);
}

sub viewTrans {
	my $xid = shift;

	my $query;
	my $ref;

	$query=$dbh->prepare('select * from trans_global where xid=?');
	$query->execute($xid);

	if ($query->rows() == 0) {
		::fatal("Bad transaction ID in viewTrans");
	}

	$ref=$query->fetchrow_hashref();

	escapedPrintf('<h1>Transaction #%d</h1>', $xid);
	::escapedPrintf('<h2>%s (%s)</h2>', $ref->{'descrip'}, $ref->{'entered'});

	$query=$dbh->prepare('select * from trans_user where xid=?');
	$query->execute($xid);

	print '<table border=1>';
	print '<tr>';
	print '<th>Confirmed</th>';
	print '<th>Name</th>';
	print '<th>Credit</th>';
	print '</tr>';
	while ($ref=$query->fetchrow_hashref()) {
		print '<tr>';
		if ($ref->{'status'} eq "confirmed") {
			print '<td align=center>*</td>';
		} else {
			print '<td>&nbsp</td>';
		}
		escapedPrintf '<td>%s</td>', ::fullName($ref->{'name'});
		escapedPrintf '<td>%m</td>', $ref->{'credit'};
		print '</tr>';
	}
	print '</table>';
}

sub fullName {
	my $id=shift;
	my $query;
	my $ref;

	$query=$dbh->prepare('select firstname,lastname from users where name=?');
	$query->execute($id);
	$ref=$query->fetchrow_hashref();
	
	return $ref->{'firstname'} . " " . $ref->{'lastname'};
}

sub passwordChangeForm {
	print <<EOF;
<h1>New Password</h1>
<form action="" method="post">
<table>
<tr><td>User ID<td><input type="text" name="name" size=8 maxlength=15 value="$name" />
<tr><td>Old Password<td><input type="password" name="password" size=8 maxlength=8 value="$password" />
<tr><td>New Password<td><input type="password" name="newpass1" size=8 maxlength=8 />
<tr><td>Again<td><input type="password" name="newpass2" size=8 maxlength=8 />
<input type="submit" name="action" value="Change Password" />
</table>
</form>
EOF

}

sub passwordCommit {
	my $query;

	my $p1 = $cgi->param('newpass1');
	my $p2 = $cgi->param('newpass2');

	if ($p1 ne $p2) {
		userError("Passwords do no match.");
	}

	$query=$dbh->prepare('update users set password=OLD_PASSWORD(?) where name=?');
	$query->execute($p1, $name);
}
	
sub confirmSession {
	
	if ($name ne "" && $password ne "") {
		# using password auth
		my $query = $dbh->prepare('select password from users where flags like "%exists%" and name=?');
		$query->execute($name);
		my $ref=$query->fetchrow_hashref();
		
		if (!$ref) {
			::userError("User \"$name\" doesn't exist.");
		}
		
		my $crypt_pwd=$ref->{'password'};

		$query = $dbh->prepare('select OLD_PASSWORD(?) as password');
		$query->execute($password);
		my $entered_pwd=$query->fetchrow_hashref()->{'password'};

		if ($crypt_pwd eq $entered_pwd) {

			my $new_session_cookie = int(rand()*1000000000); # TODO: a more secure random source
			$query=$dbh->prepare('replace auth_secrets (name,cookie) values(?, ?)');
			$query->execute($name, $new_session_cookie);
			print $cgi->header(-cookie=>$cgi->cookie(-name=>'session', -value=>$new_session_cookie, -httponly=>1));
			return;
		}
	}

	my $cookie = $cgi->cookie(-name=>'session');
	if ($cookie ne "") {
		my $query = $dbh->prepare('select name from auth_secrets where cookie=? and stamp > date_sub(now(), interval 5 minute)');
		$query->execute($cookie);

		if ($query->rows() == 0) {
			print $cgi->header(-cookie=>$cgi->cookie(-name=>'session', -value=>''));
			return "expire";
		}

		$name = $query->fetchrow_hashref()->{'name'};
		$query=$dbh->prepare('update auth_secrets set stamp=now() where name=?');
		$query->execute($name);
		return;
	}

	return 'none';
}

sub dbConnect {
	my $line;
	my ($dsn, $dbName, $dbPasswd);

	# Ghetto parser
	open HANDLE, "dbdata";
	while (<HANDLE>) {
		chop;
		s/#.*//;
		$line = $_;
		if (length($line) > 0) {
			/\s*(.*?)\s*=\s*(.*)\s*$/;
			if ($1 eq "DSN") {
				$dsn = $2;
			}
			if ($1 eq "DATABASE") {
				$dbName = $2;
			}
			if ($1 eq "PASSWORD") {
				$dbPasswd = $2;
			}
		}
	}
	close HANDLE;

	# Make sure all is ok
	$dsn ne "" or ::fatal("DSN not set in config file");
	$dbName ne "" or ::fatal("DATABASE not set in config file");
	$dbPasswd ne "" or ::fatal("PASSWORD not set in config file");

	my $dbh = DBI->connect($dsn, $dbName, $dbPasswd) or 
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
		$ret = sprintf("<font color=red>-\$%0.2f</font>",abs($num/100));
	} else {
		$ret = sprintf("\$%0.2f",$num/100);
	}
	return $ret;
}

sub armorHTMLString {
	#armors a string for HTML
	my $ret = shift;
	$ret =~ s/&/&amp;/g;
	$ret =~ s/"/&quot;/g;
	$ret =~ s/</&lt;/g;
	$ret =~ s/>/&gt;/g;
	return $ret;
}

sub unArmorHTMLString {
	#undoes the above
	my $ret = shift;
	$ret =~ s/&gt;/>/g;
	$ret =~ s/&lt;/</g;
	$ret =~ s/&quot;/"/g;
	$ret =~ s/&amp;/&/g;
	return $ret;
}

sub printHeader {
	print <<'EOF';
Content-type: text/html

<!DOCTYPE html>
<html>
	<head>
		<meta http-equiv="Content-Type" content="text/html;charset=utf-8" />
		<title>Credit Pool</title>
	</head>
EOF
}

sub fatal {
	my $msg = shift;
	print '<h1>Error</h1>', "\n";
	escapedPrintf('%s', $msg);
	print '<p>Please contact the credit pool maintainer.', "\n";
	# TODO: This should be accompanied by more information
	exit;
}

sub userError {
	my $msg = shift;
	
	print '<h1>Oops!</h1>', "\n";
	escapedPrintf('%s', $msg);
	print '<p>Hit the BACK button and give it another go.', "\n";
	# ...otherwise contact maintainer, etc...
	exit;
}

sub nonFatalUserError {
	my $msg = shift;
	escapedPrintf('%s', $msg);
	print '<br />';
}

sub footer {
	print '</body></html>';
}

sub progressHeader {
	my $current = shift;
	my $i;

	# This is bad code!  Haha!
	for ($i = 0; $i < 4; $i++) {
		if ($current == $i) {
			print '<b><font size=+2>';
		}
		if ($i == 0) {
			print 'Select Users';
		} elsif ($i == 1) {
			print 'Enter Data';
		} elsif ($i == 2) {
			print 'Confirm Transaction';
		} elsif ($i == 3) {
			print 'Finished';
		}
		if ($i < 3) {
			print ' -> ';
		}
		if ($current == $i) {
			print '</font></b>';
		}
	}
	print '<hr />', "\n";
}

sub drawChart {

	my $query;
	my $ref;
	
	my $low_bound;
	my $high_bound;
	my $increment;
	my $low_incr_bound;
	my $high_incr_bound;
	my $sum;
	my $running_sum;
	my @x_tick_labels;
	my @dataset1;
	my $chartme;
	my $date;
	my $lastdate;
	my $tick;


	$chartme=$cgi->param('chartme');
	$query=$dbh->prepare('select NOW()+0 as time');
	$query->execute();
	
	$low_bound = "20010101000000"; # start of time, Jan 2k1
	$high_bound = $query->fetchrow_hashref()->{'time'};
	$increment = "7 day";

	$low_incr_bound = $low_bound;
	$running_sum=0;
	while ($low_incr_bound < $high_bound) {
		$query=$dbh->prepare('select DATE_ADD(?, interval ?)+0 as time');
		$query->execute($low_incr_bound, $increment);
		$high_incr_bound = $query->fetchrow_hashref()->{'time'};

		$query=$dbh->prepare('select sum(credit) as sum from trans_user where name=? and entered >= ? and entered < ?');
		$query->execute($chartme, $low_incr_bound, $high_incr_bound);
		$sum=$query->fetchrow_hashref()->{'sum'}+0;
		$sum/=100;

		$running_sum += $sum;

		$query=$dbh->prepare('select date_format(?,"%b %y") as date');
		$query->execute($low_incr_bound);
		$date=$query->fetchrow_hashref->{'date'};
		
		if ($date ne $lastdate) { $tick = $date; } else { $tick = ""; }
		push(@x_tick_labels, $tick);
		push(@dataset1, $running_sum);
		
		$lastdate = $date;
		$low_incr_bound = $high_incr_bound;
	}

	my $chart = Chart::Lines->new(640, 480);
	my @data = (\@x_tick_labels, \@dataset1);
	my @labels = ($chartme);
	my %options = (
		"title" => "Weekly balance since the beginning of time (SUPER ALHPA)",
		"x_label" => "Weeks gone by...",
		"y_label" => "Debt",
		"x_ticks" => "vertical"
	);

	$chart->set(%options);
	$chart->set("legend_labels" => \@labels);
	$chart->cgi_png(\@data);
}

sub drawChart2 {

	my $query;
	my $ref;
	
	my $low_bound;
	my $high_bound;
	my $increment;
	my $low_incr_bound;
	my $high_incr_bound;
	my $sum;
	my $running_sum;
	my @x_tick_labels;
	my @dataset1;
	my @dataset2;
	my $date;
	my $lastdate;
	my $tick;

	$query=$dbh->prepare('select NOW()+0 as time');
	$query->execute();
	
	$low_bound = "20010101000000"; # start of time, Jan 2k1
	$high_bound = $query->fetchrow_hashref()->{'time'};
	$increment = "7 day";

	$low_incr_bound = $low_bound;
	$running_sum=0;
	while ($low_incr_bound < $high_bound) {
		$query=$dbh->prepare('select DATE_ADD(?, interval ?)+0 as time');
		$query->execute($low_incr_bound, $increment);
		$high_incr_bound = $query->fetchrow_hashref()->{'time'};

		$query=$dbh->prepare('select sum(abs(credit))/2 as sum from trans_user where entered >= ? and entered < ?');
		$query->execute($low_incr_bound, $high_incr_bound);
		$sum=$query->fetchrow_hashref()->{'sum'}+0;
		$sum/=100;

		$running_sum += $sum;

		$query=$dbh->prepare('select date_format(?,"%e %b %y") as date');
		$query->execute($low_incr_bound);
		$date=$query->fetchrow_hashref->{'date'};
		
		if ($date ne $lastdate) { $tick = $date; } else { $tick = ""; }
		push(@x_tick_labels, $tick);
		push(@dataset1, $sum);
		push(@dataset2, $running_sum);
		
		$lastdate=$date;
		$low_incr_bound = $high_incr_bound;
	}

	my $chart = Chart::Bars->new(2048, 480);
	my @data = (\@x_tick_labels, \@dataset1);
	my @labels = ("volume");
	my %options = (
		"title" => "Weekly volume since the beginning of time (SUPER ALHPA)",
		"x_label" => "Weeks gone by...",
		"y_label" => "Dollars per week",
		"x_ticks" => "vertical"
	);

	$chart->set(%options);
	$chart->set("legend_labels" => \@labels);
	$chart->cgi_png(\@data);
}
