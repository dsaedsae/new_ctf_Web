# Legacy Microservice Exploitation

## Challenge Description

Our company's microservice platform has been running for years. We've recently discovered that some legacy endpoints were never properly decommissioned. As part of our security audit, we need you to test these endpoints for vulnerabilities.

The platform uses a standard REST API architecture with multiple services. Start by exploring the available services and their endpoints.

## Access Information

- **Target URL**: `http://challenge.ctf.local:5000`
- **Initial Endpoint**: `/api/v2/services`

## Hints

1. Legacy systems often contain forgotten secrets
2. Flask sessions can be interesting if you know the secret
3. NoSQL databases have their own injection techniques
4. Sometimes multiple vulnerabilities need to be chained together

## Flag Format

`FLAG{...}`

## Difficulty

⭐⭐⭐⭐☆ (4/5)

---

*Note: This challenge involves multiple stages. Take your time to enumerate and understand the system.*
