---
title: Balancing delivery speed and high-quality code
subtitle: When building out new features, how do you balance speed of delivery with
  implementing higher quality yet more time-consuming code?
author: Mike
publication: Dev Details
date: September 22, 2023
---

# Balancing delivery speed and high-quality code
Someone asked me:

> When building out new features, how do you balance speed of delivery with implementing higher quality yet more time-consuming code?

At a high level, such as when designing, I try to design/envision what the end goal would look like. I think several iterations down the line. Then, I work backward from that design to figure out milestones that will get me there.

Since I know where I intend to go, I can take shortcuts. But I’m not taking blind shortcuts. I know what tradeoffs I’m making — what it will save in time now vs. cost in tech debt later.

At a low level, I optimize for speed of delivery by writing tests that validate behavior interwoven with writing code.

I'm cheating with my answer here because if you write good tests, higher-quality code naturally follows.

Starting with a test and refining it while you code allows you to develop and deliver faster. _Everything_ else to speed up delivery or improve code quality is secondary. If you have _no_ tests or _bad_ tests, you will become slower and slower each time you deliver.

## OMG is this really a post about TDD??

Not entirely. But I’ll need to explain the reasoning behind the answer to the original question.

Many people have a negative reaction to Test-Driven Development (TDD). Some might say, "If you don't like it, you're doing it wrong". Instead, let me explain a little about how I develop, and then you can see if it resonates.

[Kent Beck](https://www.kentbeck.com/) is well-known for TDD. His writings on the matter are much better than mine. He's been writing about his next book on his Substack [Software Design: Tidy First?](https://tidyfirst.substack.com/). You should check it out.

I'll give a pragmatic view of how I write tests as an integral part of coding. But first, what is a good test?

## What is a good test?

If you're writing tests with the goal of reaching some coverage metric or because the CI gods demand it, you will fail. The goal of a test is to verify behavior — not simply exercise code.

When people think "testing", they usually think "unit tests". I don't think we need unit tests as they're commonly defined for the most part:

> A unit test is a way of testing a unit - the smallest piece of code that can be logically isolated in a system.

A small piece of logically isolated code rarely does enough to be considered a useful behavior. (The exception here would be something like a low-level library. In that case, the code is generally small and logically isolated, and the user is someone who uses this library.)

 **Focus on testing behaviors — not code units.**

* * *

Behavior testing seems to be the key mind shift that people overlook. Many people get caught up with TDD because they're thinking unit tests. Writing unit tests first — for _everything_ — will result in way too many tests, too much noise, and not enough signal. It will bind your tests to the implementation. That way is the fast track to codebases no one wants to work on. You will hate it. This says more about approaches to excessive unit testing than it does about TDD.

Good tests are from the point of view of the caller (of the API, of the function, end user, etc.), and they verify a desired behavior.

This is the basics of Behavior-Driven Development (BDD).

 **Fewer unit tests; more tests of behaviors.**

* * *

Behavioral tests may result in a single test covering a large area of code when a lot of code is necessary to enact a behavior. This is okay. This is desirable (a topic for another day). It usually leads to more functional and integration testing and very little unit testing. ( _Aside: This doesn't mean use mocks — excessive mocking is an anti-pattern. Look at testing analogs or just run the dependency, e.g. SQL, on a RAM-disk instead._ )

So...

 **A good test is a test that verifies behavior.**

## Writing tests as an integral part of coding

It seems many people think test-driven development means "write the entire test first." Sometimes, they think it means "write all the tests first." The immediate follow-up to this is, "I don't know what code I'm going to write, so I don't know how to write the entire test first." Another common argument is that "TDD works when you know what you're going to build but not when you're doing a proof of concept."

These points are emphatically incorrect.

With TDD, you write a test intermingled with writing the implementation. It is what helps you figure out what the code will do. So, it works even better when you have no idea what you want the code to do.

The basics of TDD (Red; Green; Refactor):

  1. Write a test that does the behavior you're thinking of. It should fail when you run it.

  2. Write a minimal implementation to make that test pass.

  3. Consider improvements to your implementation. If there are none, go to step 1 for the next behavior.




Consider this experiment: Do not run the UI while writing server code. How would you verify your server code is working? ( _Aside: I never run the UI when I write server code._ )

You could use something like `curl`, Postman, or another API client.

The tests are my user/my API consumer/my Postman — except I can run them repeatedly on-demand.

I write a test that does one simple API call. Maybe just a `GET /api/ping`. It will fail.

I add server boilerplate and the implementation for `ping`, so now I have a repeatable API server setup.

Then I think, “Okay, what does this API need to do?” So, I write an experiment in code. I write a new test to `POST /api/thing`.

Half the time, I write what I expect the response to be. Half the time, I don't even bother to anticipate the expected result. 

I do something like `assert response == {}` in my test, which will fail when I add a body. I then do a minimal implementation and design what I want the body to return as I write the code. Then, I go back to the test, run it, visually inspect the response, and copy/paste it as the expected response.

 _Note that Kent Beck considers this practice[to be a TDD mistake](https://tidyfirst.substack.com/p/canon-tdd). I agree in principle, but practical need (developer ~~laziness~~ efficiency) often outweighs the value of principle. Handwriting an expected JSON response can be tedious. 😂_

> Mistake: copying actual, computed values & pasting them into the expected values of the test. That defeats double checking, which creates much of the validation value of TDD.

With unknown or vague requirements, I'm discovering the requirements and the implementation simultaneously. I'm designing the user interaction _and_ the implementation at the same time. 

The tests are my requirement assumptions and the user interface. I'm not trying to cover all cases, only the ones I want the user to perform and the error states I expect.

## How does writing tests like this help me deliver faster?

As long as the tests cover the business use cases — the behavior, you can write whatever fast/hacky code you need to.

The tests ensure the behavior is correct. When you have time (this is a fallacy: `later == never` — there is never time to refactor until you are forced to 😅), you can refactor the implementation safely because the tests ensure you keep the correct behavior.

To deliver faster, we can take deliberate shortcuts to get something done faster. We agree to take on tech debt that we will pay down later. This might involve writing code that will be completely thrown away or using less-than-ideal technologies in the beginning.

For the “throw-away code” aspect, this is also where tests shine. If you don’t write tests, you’re hesitant to throw away code because it’s working, and you might not actually know how it works.

So, instead of throwing away the old implementation (and keeping the tests) — which would allow you to write better faster — you keep tinkering on the old code until it is a spaghetti mess.

“throw-away code” should actually be thrown away. A new implementation should be written using what you learned from the experimental code with the tests as the driver.

## Managing risk to deliver quickly with high-quality

 _All_ code has tech debt. Accepting that tech debt is a reality and making deliberate decisions about when and where to take it on is risk management. Ignoring tech debt or blindly coding without acknowledging it exists means the tech debt is in control and decides when and where to present itself.

It’s more about deciding where to put the debt — where _I’m_ willing to take on the risk of debt.

Once it comes time to code, here is the order I think it is important to get things “right”. The later the stage, the less risk when accepting tech debt.

  1.  **The tests** — capture the business use cases and behavior.

    * Tech debt here is problematic because if you can’t write the test, you don’t understand the feature.

    * If you don’t understand the feature, you have no idea what tech debt and risks are involved.

    * It is always harder to add tests after the feature is complete because you must first figure out how it was implemented and then write tests around it — warts and all.

  2.  **The public interface** — A minimal interface that provides the operations needed by the business use cases.

    * Writing this with the tests helps you design a minimal interface.

    * You write what is needed by the business use cases instead of what might be needed.

    * The interface is hard to change once it is public — especially if we’re talking about a library or API.

    * Once in the wild, you must support that interface or force people to stop using it.

    * The smaller you make the interface, the less you have to support, which reduces tech debt.

  3.  **The implementation** — This is where it is easiest to accept tech debt.

    * Since the tests describe how it should work, and the interface is what your users are using, you can change this as much as you like, freely.

    * This includes complete rewrites and changing technologies (databases, event-based vs. HTTP, etc.).




Essentially, leave the details to the end. Tests drive the interface. The interface is essential, but not a detail. Whether it uses MySQL vs. PostgreSQL, or HTTP vs. events, or threads vs. blocking, etc. are details. The longer you wait to fill in the details, the more flexibility you have.

Good tests mean you can change the details with ease later — even if you already wrote a working implementation.

## Conclusion

To balance speed of delivery with delivering higher quality, write implementation intermingled with writing the test in a cycle.

It's the easiest way to manage risk so you can deliver code faster.

To manage risk, get things "right" in this order:

  1. Tests

  2. Public interface

  3. Implementation



