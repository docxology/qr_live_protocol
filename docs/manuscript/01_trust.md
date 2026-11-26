# Payload and trust model {#sec:trust}

Digital signatures allow the verifier to check signed data against a trusted
public key [@nist2023dss]. QRLP carries the issuer and signing-key identifier
alongside fields such as the event identifier, timestamp, sequence number,
and user data. A verifier loads the issuer key from an independently
established trust record. A key record distributed inside an untrusted
channel cannot establish the issuer by itself.

The verification result records signature status, freshness, and trust mode
separately. A local clock supplies the time reference in the offline
configuration. Other deployments can configure their own clock policies.
