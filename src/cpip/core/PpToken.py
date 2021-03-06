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

"""Represents a preprocessing Token in C/C++ source code.
"""
import copy
import sys

__author__  = 'Paul Ross'
__date__    = '2011-07-10'
__rights__  = 'Copyright (c) 2008-2017 Paul Ross'

from cpip import ExceptionCpip

class ExceptionCpipToken(ExceptionCpip):
    """Used by :py:class:`PpToken`."""
    pass

class ExceptionCpipTokenUnknownType(ExceptionCpipToken):
    """Used by :py:class:`PpToken` when the token type is out of range."""
    pass

class ExceptionCpipTokenIllegalOperation(ExceptionCpipToken):
    """Used by :py:class:`PpToken` when an illegal operation is performed."""
    pass

class ExceptionCpipTokenReopenForExpansion(
    ExceptionCpipTokenIllegalOperation
    ):
    """Used by :py:class:`PpToken` when a non-expandable token is
    made available for expansion."""
    pass

class ExceptionCpipTokenIllegalMerge(
    ExceptionCpipTokenIllegalOperation
    ):
    """Used by :py:class:`PpToken` when :py:meth:`PpToken.merge()` is called illegally."""
    pass

############################################################
# Global definitions of enumerated preprocessing token types
############################################################

#: Types of preprocessing-token
#: From: :title-reference:`ISO/IEC 14882:1998(E) 2.4 Preprocessing tokens [lex.pptoken]`
#: and :title-reference:`ISO/IEC 9899:1999 (E) 6.4.7 Header names`
#: .. note::
#: 
#:    Para 3 of the latter says that: "A header name preprocessing token is
#:    recognized only within a ``#include`` preprocessing directive."
#:
#:    So in other contexts a header-name that is a q-char-sequence should be treated
#:    as a string-literal
#:
#: This produces interesting issues in this case::
#:
#:     #define str(s) # s
#:     #include str(foo.h)
#:
#: The stringise operator creates a string-literal token but the ``#include``
#: directive expects a header-name.
#: So in certain contexts (macro stringising followed by ``#include`` instruction)
#: we need to 'downcast' a string-literal to a header-name.
#:
#: See :py:class:`cpip.core.PpLexer.PpLexer` for how this is done
LEX_PPTOKEN_TYPES = [
    'header-name',
    'identifier',
    'pp-number',
    'character-literal',
    'string-literal',
    'preprocessing-op-or-punc',
    'non-whitespace',
    # And...
    'whitespace',
    # And for concatenated tokens that have different original types
    # TODO: Justify this as in the new design of cpip token merging looks
    # a bit artificial. Is it still here just because a unit test exists?
    'concat',
]

#: Map of ``{PREPROCESS_TOKEN_TYPE : integer, ...}``
#: So this can be used thus::
#:
#:     self._cppTokType = NAME_ENUM['header-name']
NAME_ENUM = {}

#: Map of ``{integer : PREPROCESS_TOKEN_TYPE, ...}``
#: So this can be used thus::
#:
#:     if ENUM_NAME[token_type] == 'header-name':
ENUM_NAME = {}
#: Range of allowable enum values
LEX_PPTOKEN_TYPE_ENUM_RANGE = range(len(LEX_PPTOKEN_TYPES))
# Initialise maps without polluting the global namespace
# with variables.
def __initPptokenMaps():
    """Initialise the reverse map on module load.

    :returns: ``NoneType``
    """
    for i in LEX_PPTOKEN_TYPE_ENUM_RANGE:
        NAME_ENUM[LEX_PPTOKEN_TYPES[i]] = i
        ENUM_NAME[i] = LEX_PPTOKEN_TYPES[i]
__initPptokenMaps()
#################################################################
# End: Global definitions of enumerated preprocessing token types
#################################################################

############################################
# Global functions for preprocessing tokens.
############################################
def tokensStr(theTokens, shortForm=True):
    """Given a list of tokens this returns them as a string.

    :param theTokens: List of tokens.
    :type theTokens: ``list([cpip.core.PpToken.PpToken])``

    :param shortForm: If ``shortForm`` is ``True`` then the lexical string is returned.
        If ``False`` then the :py:class:`PpToken` representations separated by ' | ' is returned.
        e.g. ``PpToken(t="f", tt=identifier, line=True, prev=False, ?=False) | ...``
    :type shortForm: ``bool``

    :returns: ``str`` -- Tokens as a string.
    """
    assert(theTokens is not None)
    if shortForm:
        strList = [t.t for t in theTokens]
        return ''.join(strList)
    strList = [str(t) for t in theTokens]
    return ' | '.join(strList)

#################################################
# End: Global functions for preprocessing tokens.
#################################################

class PpToken(object):
    """Holds a preprocessor token, its type and whether the token can
    be replaced.
    
    t is the token (a string) and tt is either an enumerated integer or
    a string. Internally tt is stored as an enumerated integer.
    If the token is an identifier then it is eligible for replacement
    unless marked otherwise."""
    #: Representation of a single whitespace
    SINGLE_SPACE = ' '
    #: Operators that are replaced directly by Python equivalents for constant evaluation
    WORD_REPLACE_MAP = {
        '&&'    : ' and ', # Need whitespace for the case #if defined(__sgi)&&_COMPILER_VERSION>=700
        '||'    : ' or ', # Ditto whitespace.
        'true'  : 'True',
        'false' : 'False',
        # Python 3 support where '/' can result in a float
        '/'     : '//',
    }
    # See: ISO/IEC 14882 / N3242 :2011(E) 2.14.2 Character literals [lex.ccon], ISO/IEC 9899:2011 6.4.4.4 etc.
    CHARACTER_LITERAL_PREFIXES = {'L', 'u', 'U'}
    def __init__(self, t, tt, lineNum=0, colNum=0, isReplacement=False):
        """Constructor.
        ``t`` is the token (a string) and tt is either an enumerated integer or
        a string. Internally tt is stored as an enumerated integer.
        If the token is an identifier then it is eligible for replacement
        unless marked otherwise.

        :param t: The token.
        :type t: ``str``

        :param tt: The token type.
        :type tt: ``str``

        :param lineNum: Line number.
        :type lineNum: ``int``

        :param colNum: Column number.
        :type colNum: ``int``

        :param isReplacement: Is a token from macro replacement.
        :type isReplacement: ``bool``

        :returns: ``NoneType``
        """
        self._t = t
        # self._tt is an enumerated integer
        if tt in ENUM_NAME:
            self._tt = tt
        elif tt in NAME_ENUM:
            self._tt = NAME_ENUM[tt]
        else:
            raise ExceptionCpipTokenUnknownType(
                'Unknown token enumeration: %s' % str(tt)
                )
        self._lineNum = lineNum
        self._colNum = colNum
        # Flag to control whether this token is eligible for expansion
        # On replacement this can be set
        self._canReplace = self.isIdentifier()
        # See: http://gcc.gnu.org/onlinedocs/cppinternals/Token-Spacing.html#Token-Spacing
        self._prevWs = False
        # Flag that if True indicates that the token appeared within a section
        # that was conditionally compiled. This is False on construction and
        # can only be set True.
        self._isCond = False
        # Flag that indicates that this token is the result of macro expansion.
        # This is so the lexer can spot this situation:
        # #define PLUS +
        # +PLUS+
        # And insert whitespace to make this, correctly:
        # + + +
        # Also used for this situation:
        # #define EMPTY
        # EMPTY # include <file.h>
        # In the latter case the #include is not recognised even though it is
        # preceeded with whitespace
        self._isReplacement = isReplacement
        
    def copy(self):
        """Returns a shallow copy of self. This is useful where the same token is
        added to multiple lists and then a merge() operation on one list will
        be seen by the others. To avoid this insert self.copy() in all but one
        of the lists."""
        return copy.copy(self)

    def subst(self, t, tt):
        """Substitutes token value and type."""
        self._t = t
        if tt in ENUM_NAME:
            self._tt = tt
        elif tt in NAME_ENUM:
            self._tt = NAME_ENUM[tt]
        else:
            raise ExceptionCpipTokenUnknownType(
                'Unknown token enumeration: %s' % str(tt)
                )

    def __str__(self):
        #return '"%s", %s, %s, %s, %s' \
        #    % (self.t, self.tt, self._canReplace, self._prevWs, self._isCond)
        return 'PpToken(t="%s", tt=%s, line=%s, prev=%s, ?=%s)' \
            % (self.t.replace('\n', '\\n'), self.tt, self._canReplace, self._prevWs, self._isCond)

    def __lt__(self, other):
        return self.t < other.t or self.tt < other.tt
    
    def __eq__(self, other):
        return self.t == other.t and self.tt == other.tt
        
#    def __cmp__(self, other):
#        """Override of comparison operator.
#        Return value depends on cmp(...) used on each member."""
#        myVal = cmp(self.t, other.t)
#        if myVal:
#            return myVal
#        myVal = cmp(self.tt, other.tt)
#        if myVal:
#            return myVal
#        #myVal = cmp(self.canReplace, other.canReplace)
#        #if myVal:
#        #    return myVal
#        #myVal = cmp(self.prevWs, other.prevWs)
#        #if myVal:
#        #    return myVal
#        return 0

    def __repr__(self):
        return '"%s"' % self.t
        #return str(self)

    def isIdentifier(self):
        """:returns: ``bool`` -- ``True`` if the token type is 'identifier'."""
        return self._tt == NAME_ENUM['identifier']

    def isWs(self):
        """:returns: ``bool`` -- ``True`` if the token type is 'whitespace'."""
        return self._tt == NAME_ENUM['whitespace']

    def replaceNewLine(self):
        """Replace any newline with a single whitespace character in-place.
        
        See:
        :title-reference:`ISO/IEC 9899:1999(E) 6.10-3 and C++ ISO/IEC 14882:1998(E) 16.3-9`
        
        :returns: ``NoneType``

        :raises: :py:class:`ExceptionCpipTokenIllegalOperation` if I am not
            a whitespace token.
        """
        if self.isWs():
            self._t = self._t.replace('\n', self.SINGLE_SPACE)
        else:
            raise ExceptionCpipTokenIllegalOperation(
                'replaceNewLine() on non-whitespace token.'
                )

    def shrinkWs(self):
        """Replace all whitespace with a single ' '
        
        :returns: ``NoneType``

        :raises: :py:class:`ExceptionCpipTokenIllegalOperation` if I am not
            a whitespace token.
        """
        if self.isWs():
            self._t = self.SINGLE_SPACE
        else:
            raise ExceptionCpipTokenIllegalOperation('replaceNewLine() on non-whitespace token.')
    
    def _isOctalInteger(self, value):
        """Returns True is value is an octal digit according to:
        :title-reference:`ISO/IEC 14882:1998(E) 2.13.1 Integer literals [lex.icon] - octal-literal`.

        Value must have been shorn of integer-suffix

        :param value: The string to inspect.
        :type value: ``str``

        :returns: ``bool`` -- True if octal.
        """
        if len(value) < 2:
            return False
        if value[0] != '0':
            return False
        i = 1
        chars = set('01234567')
        while i < len(value):
            if value[i] not in chars:
                return False
            i += 1
        return True            
    
    def _convertOctalInteger(self, value):
        """If value is an octal integer then this converts it to a string
        suitable for eval(). If not the value is returned unchanged.

        :param value: String to convert.
        :type value: ``str``

        :returns: ``str`` -- String for ``eval()``.
        """
        assert self._tt == NAME_ENUM['pp-number'] or self._tt == NAME_ENUM['concat']
        assert '.' not in self._t, 'Floating point can not be octal.'
        # Handle octal with Python 3
        if sys.version_info.major == 3 and self._isOctalInteger(value):
            value = '0o' + value[1:]
        return value        
    
    def evalConstExpr(self):
        """Returns an string value suitable for eval'ing in a constant expression.
        For numbers this removes such tiresome trivia as ``'u'``, ``'L'`` etc. For others
        it replaces ``'&&'`` with ``'and'`` and so on.
        
        See
        :title-reference:`ISO/IEC ISO/IEC 14882:1998(E) 16.1 Conditional inclusion sub-section 4`
        i.e. section 16.1-4
        
        And:
        :title-reference:`ISO/IEC 9899:1999 (E) 6.10.1 Conditional
        inclusion sub-section 3`
        i.e. section 6.10.1-3

        :returns: ``str`` -- String for ``eval()``.

        :raises: ``KeyError``
        """
        # TODO: This test of 'concat' is a flakey and to get round a Linux problem
        # Need to review the whole 'concat' thing. Probably re-classify it.
        if self._tt == NAME_ENUM['pp-number'] or self._tt == NAME_ENUM['concat']:
            # Decompose the number into something that Python can evaluate.
            # This means removing suffixes like 'U' and 'L' for integers
            # and 'F' and 'L' for floats.
            # See:
            # ISO/IEC 14882:1998(E) 2.13.1 Integer literals [lex.icon]
            # ISO/IEC 14882:1998(E) 2.13.3 Floating literals [lex.fcon]
            #
            # Here we detect if it is a float by the mandatory presence of '.'
            s = self._t.lower()
            endI = 0
            if '.' in s:
                # Float
                for fSuffix in ('fl', 'lf', 'f', 'l'):
                    if s.endswith(fSuffix):
                        endI = -len(fSuffix)
                        break
                if endI != 0:
                    return self._t[:endI]
            else:
                # Integer
                for iSuffix in ('llu', 'ull', 'll', 'ul', 'lu', 'u', 'l'):
                    if s.endswith(iSuffix):
                        endI = -len(iSuffix)
                        break
                if endI != 0:
                    ret_val = self._t[:endI]
                else:
                    ret_val = self._t[:]
                return self._convertOctalInteger(ret_val)
            return self._t
        if self.isWs():
            # Remove newlines, make whitespace runs a single space
            self.shrinkWs()
            return self._t
        # Substitute 'and' for '&&'
        try:
            return self.WORD_REPLACE_MAP[self._t]
        except KeyError:
            pass
        if self.isIdentifier():
            # Return a single token translated according to:
            # ISO/IEC ISO/IEC 14882:1998(E) 16.1 Conditional inclusion sub-section 4
            # i.e. 16.1-4
            # And: ISO/IEC 9899:1999 (E) 6.10.1 Conditional inclusion sub-section 3
            # i.e. 6.10.1-3
            # returns the pp-number of 0
            return '0'
        # Strip leading 'L' etc. from character literals.
        if self._tt == NAME_ENUM['character-literal'] and len(self._t) and self._t[0] in self.CHARACTER_LITERAL_PREFIXES:
            return self._t[1:]
        return self._t

    def merge(self, other):
        """This will merge by appending the other token if they are different token
        types the type becomes 'concat'."""
        self._t += other.t
        if self.tt != other.tt:
            self._tt = NAME_ENUM['concat']
        return
    
        # TODO: Why is this here?
        #if self._tt == other.tt:
        #    self._t += other.t
        #elif self.tt == 'identifier':
        #    self._t += other.t
        #else:
        #    raise ExceptionCpipTokenIllegalMerge(
        #        'Can not merge to %s the token %s' % (self, other)
        #        )

    # Read only methods
    @property
    def t(self):
        """Returns the token as a string.

        :returns: ``str`` -- Token.
        """
        return self._t

    @property
    def tt(self):
        """Returns the token type as a string.

        :returns: ``str`` -- Token type.
        """
        return ENUM_NAME[self._tt]

    @property
    def tokEnumToktype(self):
        """Returns the token and the enumerated token type as a tuple."""
        return self._t, self._tt

    @property
    def tokToktype(self):
        """Returns the token and the token type (as a string) as a tuple."""
        return self._t, ENUM_NAME[self._tt]

    @property
    def lineNum(self):
        """Returns the line number of the start of the token as an integer."""
        return self._lineNum

    @property
    def colNum(self):
        """Returns the column number of the start of the token as an integer."""
        return self._colNum

    def getReplace(self):
        """Gets the flag that controls whether this can be replaced.

        :returns: ``bool`` -- Flag.
        """
        return self._canReplace

    # Read/write methods
    def setReplace(self, val):
        """Setter, will raise if I am not an identifier or val is True and
        if I am otherwise not expandable."""
        if not self.isIdentifier():
            raise ExceptionCpipTokenIllegalOperation(
                'setReplace when token type is "%s"' % ENUM_NAME[self._tt]
                )
        if val and not self._canReplace:
            raise ExceptionCpipTokenReopenForExpansion(
                'setReplace(True) when canReplace is already False.'
                )
        #print 'TRACE: PpToken setting %s to state: %s' % (self, val)
        #print ''.join(traceback.format_stack(limit=2))
        self._canReplace = val

    canReplace = property(
        getReplace,
        setReplace,
        None,
        'Flag to control whether this token is eligible for replacement'
        )

    def getPrevWs(self):
        """Gets the flag that records prior whitespace."""
        return self._prevWs

    def setPrevWs(self, val):
        """Sets the flag that records prior whitespace."""
        self._prevWs = val

    prevWs = property(
        getPrevWs,
        setPrevWs,
        None,
        'Flag to indicate whether this token is preceded by whitespace'
        )

    def getIsReplacement(self):
        """Gets the flag that records that this token is the result of macro replacement"""
        return self._isReplacement

    def setIsReplacement(self, val):
        """Sets the flag that records that this token is the result of macro replacement.

        :param val: Flag.
        :type val: ``bool``

        :returns: ``NoneType``
        """
        self._isReplacement = val

    isReplacement = property(
        getIsReplacement,
        setIsReplacement,
        None,
        'Flag that records that this token is the result of macro replacement'
        )

    @property
    def isCond(self):
        """Flag that if True indicates that the token appeared within a
        section that was conditionally compiled. This is False on construction
        and can only be set True by setIsCond()

        :returns: ``bool`` -- Flag.
        """
        return self._isCond

    @property
    def isUnCond(self):
        """Flag that if True indicates that the token appeared within a
        section that was un-conditionally compiled. This is the negation of
        isCond.

        :returns: ``bool`` -- Flag.
        """
        return not self._isCond

    def setIsCond(self):
        """Sets self._isCond to be True.

        :returns: ``NoneType``
        """
        self._isCond = True
