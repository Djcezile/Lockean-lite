# Lockean Lite — Authorization Boundary Decision

**Date:** 2026-08-29 UTC

## Decision

An `AUTHORIZED` authority decision is not execution permission.

Execution will require a separate proposal-bound Authorization Receipt proving the exact action Lockean evaluated and approved.

The Authorization Receipt must ultimately bind execution-relevant proposal data so that changing quantity, option legs, expiration, or another order-relevant field invalidates the authorization.

## Fail-Closed Consequence

Lockean Lite will not make the `AUTHORIZED` path reachable merely to complete the Day 1 skeleton.

Until the deterministic authority can verify every rule required for the competition vertical slice, otherwise structurally supported proposals remain:

`REJECTED — authorization_requirements_incomplete`

## Reason

A generic approval flag cannot prove what exact action was approved.

Separating the authority decision from execution permission prevents a later component from treating a broad `AUTHORIZED` result as permission to execute a changed proposal.

Paper trading does not weaken this boundary. The hackathon implementation is intended to demonstrate trustworthy architecture.