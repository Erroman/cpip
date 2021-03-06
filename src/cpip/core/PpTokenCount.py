#!/usr/bin/env python
# CPIP is a C/C++ Preprocessor implemented in Python.
# Copyright (C) 2008-2017 Paul Ross
# 
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
# 
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
# 
# Paul Ross: apaulross@gmail.com

"""Keeps a count of Preprocessing tokens.
"""

__author__  = 'Paul Ross'
__date__    = '2011-07-10'
__rights__  = 'Copyright (c) 2008-2017 Paul Ross'

from cpip import ExceptionCpip
from cpip.core import PpToken

class ExceptionPpTokenCount(ExceptionCpip):
    """Exception when handling PpTokenCount object."""
    pass

class ExceptionPpTokenCountStack(ExceptionPpTokenCount):
    """Exception when handling PpTokenCountStack object."""
    pass

class PpTokenCount(object):
    """Maps of ``{token_type : integer_count, ...}``
    self._cntrTokAll is all tokens."""
    def __init__(self):
        # Maps of {token_type : integer_count, ...}
        # self._cntrTokAll is all tokens
        self._cntrTokAll = {}
        # self._cntrTokAll is unconditional tokens
        self._cntrTokUncon = {}
        
    def __iadd__(self, other):
        """In-place add of the contents of another PpTokenCount object.

        :param other: Other object.
        :type other: :py:class:`cpip.core.PpTokenCount.PpTokenCount`

        :returns: ``cpip.core.PpTokenCount.PpTokenCount`` -- Self.
        """
        for tt in other._cntrTokAll:
            try:
                self._cntrTokAll[tt] += other._cntrTokAll[tt]
            except KeyError:
                self._cntrTokAll[tt] = other._cntrTokAll[tt]
        for tt in other._cntrTokUncon:
            try:
                self._cntrTokUncon[tt] += other._cntrTokUncon[tt]
            except KeyError:
                self._cntrTokUncon[tt] = other._cntrTokUncon[tt]
        return self
        
    def inc(self, tok, isUnCond, num=1):
        """Increment the count. tok is a PpToken, isUnCond is a boolean that is
        True if this is not conditionally compiled. num is the number of tokens
        to increment.

        :param tok: The token.
        :type tok: :py:class:`cpip.core.PpToken.PpToken`

        :param isUnCond: True if this is not conditionally compiled.
        :type isUnCond: ``bool``

        :param num: Number of tokens. Default 1.
        :type num: ``int``

        :returns: ``NoneType``
        """
        self._inc(tok.tt, isUnCond, num)
            
    def _inc(self, tokStr, isUnCond, num):
        """Increment the count. tok is a string, isUnCond is a boolean that is
        True if this is not conditionally compiled. num is the number of tokens
        to increment.

        :param tokStr: The token type.
        :type tokStr: ``str``

        :param isUnCond: True if this is not conditionally compiled.
        :type isUnCond: ``bool``

        :param num: Number of tokens.
        :type num: ``int``

        :returns: ``NoneType``
        """
        try:
            self._cntrTokAll[tokStr] += num
        except KeyError:
            self._cntrTokAll[tokStr] = num
        if isUnCond:
            try:
                self._cntrTokUncon[tokStr] += num
            except KeyError:
                self._cntrTokUncon[tokStr] = num
            
    @property
    def totalAll(self):
        """The total token count.

        :returns: ``int`` -- The count.
        """
        return sum(self._cntrTokAll.values())
    
    @property
    def totalAllUnconditional(self):
        """The token count of unconditional tokens.

        :returns: ``int`` -- The count.
        """
        return sum(self._cntrTokUncon.values())
    
    @property
    def totalAllConditional(self):
        """The token count of conditional tokens.

        :returns: ``int`` -- The count.
        """
        return sum(self._cntrTokAll.values()) - sum(self._cntrTokUncon.values())
    
    def tokenCount(self, theType, isAll):
        """Returns the token count including whitespace tokens.

        :param isAll: If ``isAll`` is ``True`` then the count of all tokens is
            returned, if ``False`` the count of unconditional tokens is returned.
        :type isAll: ``bool``

        :returns: ``int`` -- Count of tokens.
        """
        try:
            if isAll:
                return self._cntrTokAll[theType]
            else:
                return self._cntrTokUncon[theType]
        except KeyError:
            pass
        return 0
    
    def tokenCountNonWs(self, isAll):
        """Returns the token count excluding whitespace tokens.

        :param isAll: If ``isAll`` is ``True`` then the count of all tokens is
            returned, if ``False`` the count of unconditional tokens is returned.
        :type isAll: ``bool``

        :returns: ``int`` -- Count of tokens.
        """
        try:
            if isAll:
                return self.totalAll - self._cntrTokAll['whitespace']
            else:
                return self.totalAllUnconditional - self._cntrTokUncon['whitespace']
        except KeyError:
            pass
        # No whitespace tokens recorded
        if isAll:
            return self.totalAll
        return self.totalAllUnconditional
    
    def tokenTypesAndCounts(self, isAll, allPossibleTypes=True):
        """Generator the yields ``(type, count)`` in
        ``PpToken.LEX_PPTOKEN_TYPES`` order where type is a string and count an
        integer.
        
        :param isAll: If ``isAll`` is ``True`` then the count of all tokens is returned.
            If ``False`` the count of unconditional tokens is returned.
        :type isAll: ``bool``

        :param allPossibleTypes: If ``allPossibleTypes`` is ``True`` the counts of all
            token types are yielded even if zero, if ``False`` then only token types
            encountered will be yielded i.e. all counts will be non-zero.
        :type allPossibleTypes: ``bool``

        :returns: ``NoneType,tuple([str, int])`` -- Yields ``(type, count)``.
        """
        for aType in PpToken.LEX_PPTOKEN_TYPES:
            if allPossibleTypes:
                yield aType, self.tokenCount(aType, isAll)
            else:
                if isAll:
                    if aType in self._cntrTokAll:
                        yield aType, self._cntrTokAll[aType]
                else:
                    if aType in self._cntrTokUncon:
                        yield aType, self._cntrTokUncon[aType]
    
class PpTokenCountStack(object):
    """This simply holds a stack of PpTokenCount objects that can be created
    and popped of the stack."""
    def __init__(self):
        """ctor with empty stack."""
        # Stack of PpTokenCount objects
        self._stack = []
    
    def __len__(self):
        return len(self._stack)
    
    def __iadd__(self, other):
        self._stack[-1] += other
        return self
        
    def push(self):
        """Add a new counter object to the stack."""
        self._stack.append(PpTokenCount())
        
    def counter(self):
        """Returns a reference to the current PpTokenCount object.""" 
        if len(self._stack) == 0:
            raise ExceptionPpTokenCountStack('PpTokenCountStack.counter() on empty stack.')
        return self._stack[-1]
    
    def pop(self):
        """Pops the current PpTokenCount object off the stack and returns it.""" 
        if len(self._stack) == 0:
            raise ExceptionPpTokenCountStack('PpTokenCountStack.pop() on empty stack.')
        return self._stack.pop()

    def close(self):
        """Finalisation, will raise a ExceptionPpTokenCountStack if there is
        anything on the stack.""" 
        if len(self._stack) != 0:
            raise ExceptionPpTokenCountStack('PpTokenCountStack.close() on non-zero stack length [%d].' % len(self._stack))
