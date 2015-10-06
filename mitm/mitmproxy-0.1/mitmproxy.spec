Name:		mitmproxy
Version:	0.1
Release:	1%{?dist}
Summary:	Logging proxy/replay servers for Telnet, HTTP, SSL, SSH and SNMP

Group:		Development/Tools
License:	GPLv2
URL:		https://github.com/saironiq/mitmproxy
Source0:	%{name}-%{version}.tar.gz

BuildArchitectures: noarch

Requires:	filesystem bash python-twisted-core python-twisted-conch

%description
Logging proxy/replay servers for multiple protocols.

Supported protocols:
 * Telnet
 * HTTP
 * SSL
 * SSH
 * SNMP

%changelog
* Wed Jan 22 2014 Sairon Istyar <saironiq@gmail.com> 0.1-1
initial version

%prep
%setup -qc


%build
cd %{name}-%{version}
%{__python} setup.py build
cd man1
gzip mitmproxy.1


%install
cd %{name}-%{version}
%{__python} setup.py install --root=%{buildroot}
install -Dm 644 man1/mitmproxy.1.gz %{buildroot}/%{_mandir}/man1/mitmproxy.1.gz
cd %{buildroot}/%{_mandir}/man1
for proto in http snmp ssh ssl telnet ; do
  ln -s mitmproxy.1.gz mitmproxy_${proto}.1.gz
  ln -s mitmproxy.1.gz mitmreplay_${proto}.1.gz
done
for other in mitmkeygen mitmlogdiff mitmlogview fencegenlog fencetestlog ; do
  ln -s mitmproxy.1.gz ${other}.1.gz
done


%clean
rm -rf ${buildroot}


%files
%defattr(-,root,root)
%doc %{name}-%{version}/{README.md,INTERNAL.md,LICENSE}
%_mandir/man1/*.1.gz
%{python_sitelib}
%{_bindir}/*
